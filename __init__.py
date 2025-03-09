from .comfyui_mesh_simplifier import MeshSimplifierNode

NODE_CLASS_MAPPINGS = {
    "MeshSimplifierNode": MeshSimplifierNode,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "MeshSimplifierNode": "Mesh Simplifier",
}

__all__ = ['NODE_CLASS_MAPPINGS', 'NODE_DISPLAY_NAME_MAPPINGS']