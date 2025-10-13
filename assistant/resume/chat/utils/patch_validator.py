from typing import List, Optional, Any, Literal, get_origin, get_args,Type
from pydantic import BaseModel, Field, ValidationError
from copy import deepcopy
import jsonpatch



# --- 4️⃣Apply patch on copy + Pydantic validation ---
def validate_list_patches(current_list: list, patches: list[dict], model_cls: Type[BaseModel]) -> List[str]:
    errors = []

    # Convert Pydantic instances to dicts
    current_list_dicts = [item.model_dump() if isinstance(item, BaseModel) else item for item in current_list]

    # Apply on deep copy
    temp_list = deepcopy(current_list_dicts)

    try:
        patched_list = jsonpatch.apply_patch(temp_list, patches, in_place=False)
    except jsonpatch.JsonPatchException as e:
        return [f"Patch application error: {e}"]

    # Validate each patched item using Pydantic
    for idx, item in enumerate(patched_list):
        if not isinstance(item, dict):
            errors.append(f"Item at index {idx} is not a dict: {item}")
            continue
        try:
            model_cls(**item)
        except ValidationError as ve:
            errors.append(f"Item at index {idx} validation error: {ve}")

    return errors
