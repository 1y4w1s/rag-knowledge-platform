"""CLI: python -m app.eval.tool_selection_p5"""

from app.eval.tool_selection_p5.runner import write_manifest

if __name__ == "__main__":
    path = write_manifest()
    print("wrote %s" % path)
