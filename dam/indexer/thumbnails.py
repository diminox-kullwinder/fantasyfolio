"""
Thumbnail generation utilities.

Generates preview thumbnails for PDFs and 3D models.
"""

import io
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


def render_stl_thumbnail(stl_data: bytes, output_path: Optional[str] = None) -> bytes:
    """
    Render a thumbnail image from STL data.
    
    Args:
        stl_data: Raw STL file bytes
        output_path: Optional path to save the thumbnail
        
    Returns:
        PNG image bytes
    """
    try:
        import numpy as np
        from stl import mesh
        import matplotlib.pyplot as plt
        from mpl_toolkits import mplot3d
        
        # Load STL from bytes
        stl_mesh = mesh.Mesh.from_file(None, fh=io.BytesIO(stl_data))
        
        # Create figure
        fig = plt.figure(figsize=(4, 4), dpi=100)
        ax = fig.add_subplot(111, projection='3d')
        
        # Add mesh to plot
        ax.add_collection3d(mplot3d.art3d.Poly3DCollection(
            stl_mesh.vectors,
            facecolor='#4a9eff',
            edgecolor='#2a7ecf',
            linewidth=0.1,
            alpha=0.9
        ))
        
        # Auto-scale
        scale = stl_mesh.points.flatten()
        ax.auto_scale_xyz(scale, scale, scale)
        
        # Clean up axes
        ax.set_xlabel('')
        ax.set_ylabel('')
        ax.set_zlabel('')
        ax.set_axis_off()
        
        # Set viewing angle
        ax.view_init(elev=30, azim=45)
        
        plt.tight_layout(pad=0)
        
        # Save to bytes
        buf = io.BytesIO()
        plt.savefig(buf, format='png', transparent=True, bbox_inches='tight', pad_inches=0)
        plt.close(fig)
        
        buf.seek(0)
        png_data = buf.read()
        
        # Optionally save to file
        if output_path:
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, 'wb') as f:
                f.write(png_data)
        
        return png_data
        
    except ImportError:
        logger.warning("STL rendering requires: pip install numpy-stl matplotlib")
        raise
    except Exception as e:
        logger.error(f"STL thumbnail generation failed: {e}")
        raise
