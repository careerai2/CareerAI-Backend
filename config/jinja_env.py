from jinja2 import Environment, FileSystemLoader, select_autoescape

# Create a reusable Jinja environment
jinja_env = Environment(
    loader=FileSystemLoader("templates"),
    autoescape=select_autoescape(["html", "xml"]),
    trim_blocks=True,
    lstrip_blocks=True
)
