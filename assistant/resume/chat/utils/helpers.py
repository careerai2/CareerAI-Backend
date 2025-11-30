# from config.redis_config import redis_client as r
from config.redis_config import redis_service
from websocket_manger import ConnectionManager
from app_instance import app
import json
from models.resume_model import * 
from utils.mapper import resume_section_map,ResumeSectionLiteral,Fields
import jsonpatch
from pydantic import ValidationError
import jsonpointer
from .update_summar_skills import update_summary_and_skills
import re
import json
from typing import Optional, Dict, Any


def extract_json_from_response(content: str) -> Optional[Dict[str, Any]]:
    """Extract JSON from LLM response using multiple patterns."""
    patterns = [
        r"```json\s*([\s\S]*?)\s*```",  # JSON fenced block
        r"```\s*([\s\S]*?)\s*```",      # Generic fenced block
        r"(\{[\s\S]*\})"                # Any JSON object (greedy, multiline)
    ]
    
    for pattern in patterns:
        matches = re.findall(pattern, content, re.DOTALL | re.IGNORECASE)
        for match in matches:
            try:
                return json.loads(match.strip())
            except json.JSONDecodeError as e:
                # print(f"Failed to parse with error: {e}")  # Debug if needed
                continue
    
    print("No valid JSON found in response")
    return None


async def retrive_entry_from_resume(
    threadId: str,
    section: ResumeSectionLiteral,
    entryIndex: Optional[int] = None
):
    try:
        resume = redis_service.get_resume_by_threadId(threadId)
        
        if not resume:
            return None

        # Handle summary separately
        if section == "summary":
            return {"summary":resume.get("summary", {})}

        # For other sections, ensure entryIndex is provided
        if (section != "summary" and entryIndex is None):
            print("Invalid entry index")
            return None

        # Access the section safely
        section_entries = resume.get(section, [])
        
        if entryIndex is None:
            return section_entries
        
        if entryIndex >= len(section_entries):
            print(f"Entry index {entryIndex} out of range for section {section}")
            return None

        return section_entries[entryIndex]

    except Exception as e:
        print(f"Error while retrieving the entry. Error msg: {e}")
        return None


def get_patch_field_and_index(patch_path: str):
    """
    Extracts internship index and field from a JSON Patch path.
    Handles:
      - "/0/company_name" -> index=0, field='company_name'
      - "/1/role" -> index=1, field='role'
      - "/internship_work_description_bullets" -> index=None, field='internship_work_description_bullets'
      - "/-" -> index=None, field=None (append operation)
      - "/1/internship_work_description_bullets/-" -> index=1, field='internship_work_description_bullets', append=True
    Returns:
      index: int | None
      field: str | None
      append: bool
    """
    parts = patch_path.lstrip("/").split("/")
    append = False
    
    if not parts:
        return None, None, False
    
    # Check if the last part is '-' -> append operation
    if parts[-1] == "-":
        append = True
        parts = parts[:-1]  # remove the '-' to get actual field
    
    if not parts:
        # Path was just "/-"
        return None, None, append
    
    # First part is index if digit
    if parts[0].isdigit():
        index = int(parts[0])
        field = parts[1] if len(parts) > 1 else None
        return index, field, append
    
    # Path without index
    return None, parts[-1], append


def get_unique_indices(patch_list: List[Dict]) -> List[int]:
    indices = set()
    import re
    for patch in patch_list:
        match = re.match(r"^/(\d+)(/.*)?$", patch["path"])
        if match:
            indices.add(int(match.group(1)))
    return list(indices)
