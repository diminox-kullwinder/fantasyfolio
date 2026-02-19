"""
Thumbnail generation utilities.

Generates preview thumbnails for PDFs and 3D models (STL, OBJ, 3MF).
"""

import io
import logging
import re
import zipfile
from pathlib import Path
from typing import Optional, Tuple
from xml.etree import ElementTree

import numpy as np
from PIL import Image, ImageDraw

logger = logging.getLogger(__name__)


def render_with_stl_thumb(data: bytes, format: str, output_path: str, size: int = 512) -> bytes:
    """
    Render 3D model thumbnail using f3d (preferred) or stl-thumb CLI.
    Supports STL, OBJ, and 3MF formats.
    Falls back to PIL if both fail.
    """
    import subprocess
    import tempfile
    import shutil
    
    # Write to temp file with correct extension
    suffix = f'.{format.lower()}'
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
        f.write(data)
        model_path = f.name
    
    try:
        # Try f3d first (works headless in containers with xvfb)
        if shutil.which('f3d') and shutil.which('xvfb-run'):
            try:
                # Camera direction: front view, slightly from above (good for miniatures)
                result = subprocess.run(
                    ['xvfb-run', '-a', 'f3d', 
                     '--output', output_path, 
                     '--resolution', f'{size},{size}', 
                     '--up', '+Z',
                     '--camera-direction=0,-1,-0.3',  # Front view, slight downward angle
                     model_path],
                    capture_output=True,
                    timeout=60
                )
                if result.returncode == 0 and Path(output_path).exists():
                    with open(output_path, 'rb') as f:
                        return f.read()
            except Exception as e:
                logger.debug(f"f3d failed, trying stl-thumb: {e}")
        
        # Fall back to stl-thumb
        timeout = 60 if format.lower() == '3mf' else 30
        result = subprocess.run(
            ['stl-thumb', '-s', str(size), model_path, output_path],
            capture_output=True,
            timeout=timeout
        )
        
        if result.returncode == 0 and Path(output_path).exists():
            with open(output_path, 'rb') as f:
                return f.read()
        else:
            raise RuntimeError(f"stl-thumb failed: {result.stderr.decode()}")
    finally:
        # Clean up temp file
        Path(model_path).unlink(missing_ok=True)


def parse_stl(data: bytes) -> np.ndarray:
    """Parse STL file and return triangles as numpy array."""
    from stl import mesh
    stl_mesh = mesh.Mesh.from_file(None, fh=io.BytesIO(data))
    return stl_mesh.vectors


def parse_obj(data: bytes) -> np.ndarray:
    """Parse OBJ file and return triangles as numpy array."""
    text = data.decode('utf-8', errors='ignore')
    
    vertices = []
    faces = []
    
    for line in text.split('\n'):
        line = line.strip()
        if line.startswith('v '):
            parts = line.split()[1:4]
            vertices.append([float(p) for p in parts])
        elif line.startswith('f '):
            # Face can be: f 1 2 3 or f 1/1/1 2/2/2 3/3/3
            parts = line.split()[1:]
            face_verts = []
            for p in parts:
                # Get vertex index (before any /)
                idx = int(p.split('/')[0])
                # OBJ indices are 1-based
                face_verts.append(idx - 1)
            # Triangulate if more than 3 vertices (fan triangulation)
            for i in range(1, len(face_verts) - 1):
                faces.append([face_verts[0], face_verts[i], face_verts[i + 1]])
    
    if not vertices or not faces:
        raise ValueError("No valid geometry found in OBJ file")
    
    vertices = np.array(vertices)
    triangles = np.array([[vertices[f[0]], vertices[f[1]], vertices[f[2]]] for f in faces])
    return triangles


def parse_3mf(data: bytes) -> np.ndarray:
    """Parse 3MF file and return triangles as numpy array."""
    # 3MF is a ZIP containing XML files
    with zipfile.ZipFile(io.BytesIO(data), 'r') as zf:
        # Find the model file
        model_file = None
        for name in zf.namelist():
            if name.endswith('.model') or '/3D/' in name:
                model_file = name
                break
        
        if not model_file:
            # Try common paths
            for path in ['3D/3dmodel.model', '3dmodel.model']:
                if path in zf.namelist():
                    model_file = path
                    break
        
        if not model_file:
            raise ValueError("No model file found in 3MF archive")
        
        xml_data = zf.read(model_file)
    
    # Parse XML
    root = ElementTree.fromstring(xml_data)
    
    # Handle namespace
    ns = {'m': 'http://schemas.microsoft.com/3dmanufacturing/core/2015/02'}
    
    vertices = []
    triangles = []
    
    # Find mesh elements
    for mesh_elem in root.iter():
        if mesh_elem.tag.endswith('mesh'):
            # Get vertices
            for vert_elem in mesh_elem.iter():
                if vert_elem.tag.endswith('vertex'):
                    x = float(vert_elem.get('x', 0))
                    y = float(vert_elem.get('y', 0))
                    z = float(vert_elem.get('z', 0))
                    vertices.append([x, y, z])
            
            # Get triangles
            for tri_elem in mesh_elem.iter():
                if tri_elem.tag.endswith('triangle'):
                    v1 = int(tri_elem.get('v1', 0))
                    v2 = int(tri_elem.get('v2', 0))
                    v3 = int(tri_elem.get('v3', 0))
                    triangles.append([v1, v2, v3])
    
    if not vertices or not triangles:
        raise ValueError("No valid geometry found in 3MF file")
    
    vertices = np.array(vertices)
    tri_array = np.array([[vertices[t[0]], vertices[t[1]], vertices[t[2]]] for t in triangles])
    return tri_array


def render_mesh_thumbnail(triangles: np.ndarray, output_path: Optional[str] = None, size: int = 512) -> bytes:
    """
    Render a thumbnail from triangles using 2D projection.
    
    Args:
        triangles: Nx3x3 array of triangle vertices
        output_path: Optional path to save the thumbnail
        size: Image size in pixels (square)
        
    Returns:
        PNG image bytes
    """
    # Sample if too many triangles (higher = better quality, slower)
    max_triangles = 20000
    if len(triangles) > max_triangles:
        indices = np.random.choice(len(triangles), max_triangles, replace=False)
        triangles = triangles[indices]
    
    # Get all vertices for bounds calculation
    vertices = triangles.reshape(-1, 3)
    
    # Isometric projection (rotate 45° around Y, then 35° around X)
    angle_y = np.radians(45)
    angle_x = np.radians(35)
    
    cos_y, sin_y = np.cos(angle_y), np.sin(angle_y)
    rot_y = np.array([
        [cos_y, 0, sin_y],
        [0, 1, 0],
        [-sin_y, 0, cos_y]
    ])
    
    cos_x, sin_x = np.cos(angle_x), np.sin(angle_x)
    rot_x = np.array([
        [1, 0, 0],
        [0, cos_x, -sin_x],
        [0, sin_x, cos_x]
    ])
    
    # Apply rotations to all vertices for bounds
    rotated = vertices @ rot_y.T @ rot_x.T
    projected = rotated[:, :2]
    
    min_coords = projected.min(axis=0)
    max_coords = projected.max(axis=0)
    range_coords = max_coords - min_coords
    range_coords[range_coords == 0] = 1
    
    padding = 0.1
    
    # Create image
    img = Image.new('RGB', (size, size), '#2a2a3e')
    draw = ImageDraw.Draw(img)
    
    # Sort triangles by depth (painter's algorithm) - draw far triangles first
    # Calculate centroid Z for each triangle after rotation
    tri_depths = []
    for tri in triangles:
        rotated_tri = tri @ rot_y.T @ rot_x.T
        centroid_z = rotated_tri[:, 2].mean()
        tri_depths.append(centroid_z)
    
    # Sort by depth (furthest first)
    sorted_indices = np.argsort(tri_depths)
    triangles = triangles[sorted_indices]
    
    # Draw triangles (now in depth order)
    for tri in triangles:
        rotated_tri = tri @ rot_y.T @ rot_x.T
        proj_tri = rotated_tri[:, :2]
        
        norm_tri = (proj_tri - min_coords) / range_coords
        norm_tri = norm_tri * (1 - 2 * padding) + padding
        img_tri = (norm_tri * size).astype(int)
        
        points = [tuple(p) for p in img_tri]
        
        # Depth shading
        normal = np.cross(tri[1] - tri[0], tri[2] - tri[0])
        norm_len = np.linalg.norm(normal)
        if norm_len > 0:
            normal = normal / norm_len
        brightness = abs(normal[2]) * 0.5 + 0.5
        
        r = int(74 * brightness)
        g = int(158 * brightness)
        b = int(255 * brightness)
        
        draw.polygon(points, fill=(r, g, b), outline=(42, 126, 207))
    
    # Save to bytes
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)
    png_data = buf.read()
    
    if output_path:
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'wb') as f:
            f.write(png_data)
    
    return png_data


def render_3d_thumbnail(data: bytes, format: str, output_path: Optional[str] = None, size: int = 512) -> bytes:
    """
    Render a thumbnail for any supported 3D format.
    
    Uses stl-thumb (OpenGL) for high quality renders, falls back to PIL.
    
    Args:
        data: Raw file bytes
        format: File format ('stl', 'obj', '3mf', 'glb', 'gltf', 'dae', '3ds', 'ply', 'x3d')
        output_path: Optional path to save the thumbnail
        size: Image size in pixels
        
    Returns:
        PNG image bytes
    """
    format = format.lower()
    
    if format not in ('stl', 'obj', '3mf', 'glb', 'gltf', 'dae', '3ds', 'ply', 'x3d'):
        raise ValueError(f"Unsupported format: {format}")
    
    # Try stl-thumb first (high quality OpenGL rendering)
    try:
        import tempfile
        if output_path:
            return render_with_stl_thumb(data, format, output_path, size)
        else:
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as f:
                tmp_path = f.name
            png_data = render_with_stl_thumb(data, format, tmp_path, size)
            Path(tmp_path).unlink(missing_ok=True)
            return png_data
    except Exception as e:
        logger.warning(f"stl-thumb failed for {format}, falling back to PIL: {e}")
    
    # Fallback to PIL rendering (only for formats we can parse)
    if format == 'stl':
        triangles = parse_stl(data)
    elif format == 'obj':
        triangles = parse_obj(data)
    elif format == '3mf':
        triangles = parse_3mf(data)
    elif format in ('glb', 'gltf'):
        # GLB/glTF requires f3d - no PIL fallback available
        raise RuntimeError(f"f3d failed and no PIL fallback available for {format}")
    else:
        raise ValueError(f"No parser available for format: {format}")
    
    return render_mesh_thumbnail(triangles, output_path, size)


# Keep backward compatibility
def render_stl_thumbnail(stl_data: bytes, output_path: Optional[str] = None, size: int = 512) -> bytes:
    """Render STL thumbnail (backward compatible)."""
    return render_3d_thumbnail(stl_data, 'stl', output_path, size)
