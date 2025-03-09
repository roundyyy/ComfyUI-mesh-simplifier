"""
ComfyUI Mesh Simplifier Node
This node uses PyMeshLab for mesh simplification with texture preservation.

PyMeshLab is released under the GPL License.
PyMeshLab Copyright:
   PyMeshLab
   All rights reserved.

   VCGLib  http://www.vcglib.net                                     o o
   Visual and Computer Graphics Library                            o     o
                                                                  _   O  _
   Paolo Cignoni                                                    \/)\/
   Visual Computing Lab  http://vcg.isti.cnr.it                    /\/|
   ISTI - Italian National Research Council                           |
   Copyright(C) 2020                                                  \
"""

import os
import sys
import tempfile
import time
import numpy as np
import trimesh
import pymeshlab
import torch

# Node information
MANIFEST = {
    "name": "ComfyUI-Mesh-Simplifier",
    "version": (0, 1, 0),
    "author": "roundyyy",
    "project": "https://github.com/roundyyy/comfyui-mesh-simplifier",
    "description": "A node for ComfyUI that simplifies 3D meshes with texture preservation using PyMeshLab",
}

class MeshSimplifierNode:
    """
    ComfyUI node that simplifies 3D meshes using PyMeshLab's Quadric Edge Collapse Decimation algorithm.
    Takes a mesh input from ComfyUI-3D-Pack and returns a simplified mesh with texture preservation.
    """
    
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "mesh": ("MESH",),  # Input mesh from Comfy3D
                "simplify_method": (["target_faces", "percentage_reduction"], {"default": "target_faces"}),
                "target_faces": ("INT", {"default": 1000, "min": 10, "max": 1000000, "step": 100}),
                "percentage_reduction": ("FLOAT", {"default": 0.75, "min": 0.01, "max": 0.99, "step": 0.01}),
                "quality_threshold": ("FLOAT", {"default": 0.5, "min": 0.1, "max": 1.0, "step": 0.1}),
                "texture_weight": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 2.0, "step": 0.1}),
                "preserve_boundary": (["True", "False"], {"default": "True"}),
                "boundary_weight": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 2.0, "step": 0.1}),
                "optimal_position": (["True", "False"], {"default": "True"}),
                "preserve_normal": (["True", "False"], {"default": "True"}),
                "planar_simplification": (["True", "False"], {"default": "True"}),
                "pre_clean": (["True", "False"], {"default": "True"}),
            }
        }

    RETURN_TYPES = ("MESH",)
    RETURN_NAMES = ("simplified_mesh",)
    FUNCTION = "simplify_mesh"
    CATEGORY = "3D/Mesh"
    
    DESCRIPTION = """Simplifies 3D meshes with texture preservation using PyMeshLab's Quadric Edge Collapse Decimation algorithm.
    
This node allows you to reduce the complexity of 3D meshes while preserving visual quality and textures.
Works with any mesh from ComfyUI-3D-Pack nodes (StableFast3D, Hunyuan3D, etc.).

- Simplify by target face count or percentage reduction
- Preserves textures and UV maps when possible
- Pre-cleans meshes to fix common issues
- Compatible with textured and non-textured meshes

When using this tool in academic projects, please cite PyMeshLab:
@software{pymeshlab, author={Alessandro Muntoni and Paolo Cignoni}, title={{PyMeshLab}}, 
month=jan, year=2021, publisher={Zenodo}, doi={10.5281/zenodo.4438750}}
"""

    def _bool_str_to_bool(self, bool_str):
        """Convert string bool representation to actual boolean"""
        return bool_str == "True"

    def simplify_mesh(self, mesh, simplify_method, target_faces, percentage_reduction, 
                    quality_threshold, texture_weight, preserve_boundary, boundary_weight,
                    optimal_position, preserve_normal, planar_simplification, pre_clean):
        """
        Simplify the input mesh using PyMeshLab through temporary OBJ files.
        
        Args:
            mesh: ComfyUI/Comfy3D mesh object
            Other parameters: Correspond to simplification parameters
            
        Returns:
            simplified_mesh: The simplified mesh in a format compatible with ComfyUI-3D-Pack
        """
        # Convert string representations of booleans to actual booleans
        preserve_boundary = self._bool_str_to_bool(preserve_boundary)
        optimal_position = self._bool_str_to_bool(optimal_position)
        preserve_normal = self._bool_str_to_bool(preserve_normal)
        planar_simplification = self._bool_str_to_bool(planar_simplification)
        pre_clean = self._bool_str_to_bool(pre_clean)
        
        # Set target faces or percentage reduction based on simplify_method
        if simplify_method == "target_faces":
            target_faces_val = int(target_faces)
            percentage_reduction_val = None
        else:  # percentage_reduction
            target_faces_val = None
            percentage_reduction_val = float(percentage_reduction)
        
        # Create temporary OBJ files
        with tempfile.NamedTemporaryFile(suffix='.obj', delete=False) as tmp:
            input_obj = tmp.name
        with tempfile.NamedTemporaryFile(suffix='.obj', delete=False) as tmp:
            output_obj = tmp.name
        
        try:
            # Print mesh stats before simplification
            print(f"Original mesh: {len(mesh.v):,} vertices, {len(mesh.f):,} faces")
            has_texture = hasattr(mesh, 'vt') and mesh.vt is not None and mesh.ft is not None
            if has_texture:
                print(f"Mesh has texture coordinates: {len(mesh.vt):,} texture vertices")
            else:
                print("Mesh does not have texture coordinates")
            
            # Save the mesh to OBJ format
            print(f"Saving mesh to temporary OBJ file: {input_obj}")
            mesh.write_obj(input_obj)
            
            # Simplify the mesh
            print(f"Simplifying mesh...")
            
            if has_texture:
                # Use texture-preserving simplification for meshes with textures
                print("Using texture-preserving simplification")
                self._simplify_with_texture(
                    input_obj, 
                    output_obj, 
                    target_faces_val, 
                    percentage_reduction_val,
                    quality_threshold,
                    texture_weight,
                    preserve_boundary,
                    boundary_weight,
                    optimal_position,
                    preserve_normal,
                    planar_simplification,
                    pre_clean
                )
            else:
                # Use standard simplification for meshes without textures
                print("Using standard simplification without texture preservation")
                self._simplify_without_texture(
                    input_obj, 
                    output_obj, 
                    target_faces_val, 
                    percentage_reduction_val,
                    quality_threshold,
                    preserve_boundary,
                    boundary_weight,
                    optimal_position,
                    preserve_normal,
                    planar_simplification,
                    pre_clean
                )
            
            # Load the simplified mesh back into ComfyUI-3D-Pack format
            print(f"Loading simplified mesh from temporary OBJ file: {output_obj}")
            simplified_mesh = type(mesh).load(output_obj, resize=False, renormal=True, retex=False)
            
            # Copy any attributes from the original mesh that might not have been saved to OBJ
            for attr in ['device', 'ori_center', 'ori_scale']:
                if hasattr(mesh, attr):
                    setattr(simplified_mesh, attr, getattr(mesh, attr))
            
            # Transfer texture from original mesh if available
            if hasattr(mesh, 'albedo') and mesh.albedo is not None:
                simplified_mesh.albedo = mesh.albedo
                print("Transferred texture from original mesh")
            
            # Transfer metallic-roughness map if available
            if hasattr(mesh, 'metallicRoughness') and mesh.metallicRoughness is not None:
                simplified_mesh.metallicRoughness = mesh.metallicRoughness
                print("Transferred metallic-roughness map from original mesh")
            
            # Make sure we're using the same device as the original mesh
            if hasattr(mesh, 'device'):
                simplified_mesh = simplified_mesh.to(mesh.device)
            
            # Print mesh stats after simplification
            print(f"Simplified mesh: {len(simplified_mesh.v):,} vertices, {len(simplified_mesh.f):,} faces")
            if hasattr(simplified_mesh, 'vt') and simplified_mesh.vt is not None:
                print(f"Simplified mesh has texture coordinates: {len(simplified_mesh.vt):,} texture vertices")
            
            return (simplified_mesh,)
        finally:
            # Clean up the temporary files
            if os.path.exists(input_obj):
                os.remove(input_obj)
            if os.path.exists(output_obj):
                os.remove(output_obj)
    
    def _simplify_with_texture(self, input_path, output_path, target_faces, percentage_reduction,
                             quality_threshold, texture_weight, preserve_boundary, boundary_weight,
                             optimal_position, preserve_normal, planar_simplification, pre_clean):
        """
        Simplify a mesh with texture preservation.
        """
        # Create a MeshSet
        ms = pymeshlab.MeshSet()
        
        # Load the mesh
        ms.load_new_mesh(input_path)
        
        # Get current face count for calculation
        current_faces = ms.current_mesh().face_number()
        current_vertices = ms.current_mesh().vertex_number()
        
        print(f"Loaded mesh: {current_vertices:,} vertices, {current_faces:,} faces")
        
        # Pre-processing step to clean the mesh
        if pre_clean:
            print(f"Performing pre-processing cleaning operations...")
            
            # Merge close vertices (helps with many common mesh issues)
            ms.apply_filter('meshing_merge_close_vertices')
            
            # Remove unreferenced vertices
            ms.apply_filter('meshing_remove_unreferenced_vertices')
            
            # Remove duplicate faces if they exist
            ms.apply_filter('meshing_remove_duplicate_faces')
            
            # Update counts after pre-processing
            cleaned_vertices = ms.current_mesh().vertex_number()
            cleaned_faces = ms.current_mesh().face_number()
            
            # Report the effect of pre-processing
            vertices_removed = current_vertices - cleaned_vertices
            faces_removed = current_faces - cleaned_faces
            
            if vertices_removed > 0 or faces_removed > 0:
                print(f"Pre-processing removed {vertices_removed:,} vertices and {faces_removed:,} faces")
                print(f"Mesh after cleaning: {cleaned_vertices:,} vertices, {cleaned_faces:,} faces")
            else:
                print("Pre-processing complete. No issues found in the mesh.")
            
            # Update current faces count for target calculation
            current_faces = cleaned_faces
        
        # Calculate target face count
        if target_faces is not None and target_faces > 0:
            targetfacenum = int(target_faces)
        elif percentage_reduction is not None and 0.0 <= percentage_reduction <= 1.0:
            targetfacenum = int(current_faces * (1.0 - percentage_reduction))
        else:
            # Default case
            targetfacenum = int(target_faces) if target_faces is not None else 1000
            
        # Ensure we don't go below a minimum number of faces
        targetfacenum = max(4, targetfacenum)
        
        print(f"Starting mesh simplification (current: {current_faces:,} faces, target: {targetfacenum:,} faces)...")
        start_time = time.time()
        
        try:
            # Use the texture-preserving filter 
            ms.apply_filter('meshing_decimation_quadric_edge_collapse_with_texture', 
                        targetfacenum=targetfacenum,
                        qualitythr=float(quality_threshold),
                        extratcoordw=float(texture_weight),
                        preserveboundary=preserve_boundary,
                        boundaryweight=float(boundary_weight),
                        optimalplacement=optimal_position,
                        preservenormal=preserve_normal,
                        planarquadric=planar_simplification)
            
            # Optional: Quality improvement as post-processing
            ms.apply_filter('meshing_edge_flip_by_planar_optimization',
                        planartype='area/max side',
                        pthreshold=1.0,
                        iterations=2)
        except Exception as e:
            print(f"Warning: Texture simplification failed with error: {e}")
            print("Falling back to standard simplification...")
            
            # Fall back to standard simplification if texture simplification fails
            self._simplify_without_texture(
                input_path, 
                output_path, 
                target_faces, 
                percentage_reduction,
                quality_threshold,
                preserve_boundary,
                boundary_weight,
                optimal_position,
                preserve_normal,
                planar_simplification,
                False  # Don't do pre-clean again
            )
            return
        
        elapsed = time.time() - start_time
        new_faces = ms.current_mesh().face_number()
        reduction_percent = ((current_faces - new_faces) / current_faces) * 100
        
        print(f"Mesh simplification completed in {elapsed:.2f} seconds.")
        print(f"Reduced from {current_faces:,} to {new_faces:,} faces ({reduction_percent:.1f}% reduction)")
        
        # Save the mesh
        ms.save_current_mesh(output_path)
    
    def _simplify_without_texture(self, input_path, output_path, target_faces, percentage_reduction,
                                quality_threshold, preserve_boundary, boundary_weight,
                                optimal_position, preserve_normal, planar_simplification, pre_clean):
        """
        Simplify a mesh without texture preservation.
        """
        # Create a MeshSet
        ms = pymeshlab.MeshSet()
        
        # Load the mesh
        ms.load_new_mesh(input_path)
        
        # Get current face count for calculation
        current_faces = ms.current_mesh().face_number()
        current_vertices = ms.current_mesh().vertex_number()
        
        print(f"Loaded mesh: {current_vertices:,} vertices, {current_faces:,} faces")
        
        # Pre-processing step to clean the mesh
        if pre_clean:
            print(f"Performing pre-processing cleaning operations...")
            
            # Merge close vertices (helps with many common mesh issues)
            ms.apply_filter('meshing_merge_close_vertices')
            
            # Remove unreferenced vertices
            ms.apply_filter('meshing_remove_unreferenced_vertices')
            
            # Remove duplicate faces if they exist
            ms.apply_filter('meshing_remove_duplicate_faces')
            
            # Update counts after pre-processing
            cleaned_vertices = ms.current_mesh().vertex_number()
            cleaned_faces = ms.current_mesh().face_number()
            
            # Report the effect of pre-processing
            vertices_removed = current_vertices - cleaned_vertices
            faces_removed = current_faces - cleaned_faces
            
            if vertices_removed > 0 or faces_removed > 0:
                print(f"Pre-processing removed {vertices_removed:,} vertices and {faces_removed:,} faces")
                print(f"Mesh after cleaning: {cleaned_vertices:,} vertices, {cleaned_faces:,} faces")
            else:
                print("Pre-processing complete. No issues found in the mesh.")
            
            # Update current faces count for target calculation
            current_faces = cleaned_faces
        
        # Calculate target face count
        if target_faces is not None and target_faces > 0:
            targetfacenum = int(target_faces)
        elif percentage_reduction is not None and 0.0 <= percentage_reduction <= 1.0:
            targetfacenum = int(current_faces * (1.0 - percentage_reduction))
        else:
            # Default case
            targetfacenum = int(target_faces) if target_faces is not None else 1000
            
        # Ensure we don't go below a minimum number of faces
        targetfacenum = max(4, targetfacenum)
        
        print(f"Starting standard mesh simplification (current: {current_faces:,} faces, target: {targetfacenum:,} faces)...")
        start_time = time.time()
        
        # Use the standard quadric edge collapse filter
        ms.apply_filter('meshing_decimation_quadric_edge_collapse', 
                    targetfacenum=targetfacenum,
                    qualitythr=float(quality_threshold),
                    preserveboundary=preserve_boundary,
                    boundaryweight=float(boundary_weight),
                    optimalplacement=optimal_position,
                    preservenormal=preserve_normal,
                    planarquadric=planar_simplification)
        
        # Optional: Quality improvement as post-processing
        ms.apply_filter('meshing_edge_flip_by_planar_optimization',
                    planartype='area/max side',
                    pthreshold=1.0,
                    iterations=2)
        
        elapsed = time.time() - start_time
        new_faces = ms.current_mesh().face_number()
        reduction_percent = ((current_faces - new_faces) / current_faces) * 100
        
        print(f"Mesh simplification completed in {elapsed:.2f} seconds.")
        print(f"Reduced from {current_faces:,} to {new_faces:,} faces ({reduction_percent:.1f}% reduction)")
        
        # Save the mesh
        ms.save_current_mesh(output_path)