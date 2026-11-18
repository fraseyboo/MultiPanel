import numpy as np
import cv2
import matplotlib.pyplot as plt
import sys
import os
from tqdm import tqdm
# import numpy as np
# import cv2
# import matplotlib.pyplot as plt
from shapely.geometry import Polygon

import triangle as tr
import svgpathtools
import vtk
import re
import logging

logger = logging.getLogger(__name__)




# ----------------------------
# PARAMETERS
# ----------------------------
# IMAGE_PATH = "input.png"
IMAGE_PATH = os.path.join(
    os.path.dirname(__file__), "icons", "png_icons", "hexagonal_prism.png")

# ----------------------------
# PARAMETERS
# ----------------------------

# EPSILON_FACTOR = 0.003   # contour simplification (smaller = more detail)
EPSILON_FACTOR = 0.00001   # contour simplification (smaller = more detail)
MIN_AREA = 0.01        # ignore tiny shapes
OUTPUT_FILE = "vector_triangles.txt"
MAX_COLORS = 10       # max colors to quantize to (for simple icons, 20 is usually enough)



def simplify(cnt, eps_factor):
    """Execute the simplify operation."""
    epsilon = eps_factor * cv2.arcLength(cnt, True)
    approx = cv2.approxPolyDP(cnt, epsilon, True)
    pts = approx.squeeze()

    if len(pts.shape) != 2 or len(pts) < 3:
        return None

    return pts.astype(float)

def remove_collinear(points, eps=1e-6):

    """Remove collinear."""
    if len(points) < 3:
        return points

    cleaned = []

    n = len(points)

    for i in range(n):

        p0 = points[i - 1]
        p1 = points[i]
        p2 = points[(i + 1) % n]

        v1 = p1 - p0
        v2 = p2 - p1

        cross = abs(v1[0]*v2[1] - v1[1]*v2[0])

        if cross > eps:
            cleaned.append(p1)

    return np.array(cleaned)


def convert_image_to_triangles(image_path, max_colors=10, min_area=0.01, show_plots=True, ignore_background=False, background_color=None):
    # ----------------------------
    # LOAD IMAGE
    # ----------------------------

    """Convert image to triangles."""
    assert os.path.exists(image_path), f"Image not found: {image_path}"

    img = cv2.imread(image_path)
    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    image_height, image_width, _ = img.shape

    # ----------------------------
    # COLOR SEGMENTATION
    # (for simple images this works well)
    # ----------------------------
    # Convert to few colors

    # treat transparent pixels as magenta (or any color not present in the image) so they get their own cluster
    if img.shape[2] > 3:  # if image has alpha channel

        alpha_channel = cv2.imread(image_path, cv2.IMREAD_UNCHANGED)[:,:,3]  # get alpha channel
        transparent_mask = (alpha_channel == 0)
        if background_color is None:
            background_color = [255, 0, 255]  # default magenta for transparent pixels
        img[transparent_mask] = background_color  # set transparent pixels to background color

    Z = img.reshape((-1,3)).astype(np.float32)

    _, labels, centers = cv2.kmeans(Z, max_colors, None,
                                    (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 10, 1.0),
                                    10, cv2.KMEANS_RANDOM_CENTERS)

    quant = centers[labels.flatten()].reshape((image_height, image_width, 3)).astype(np.uint8)
    label_map = labels.reshape(image_height, image_width)


    if ignore_background:
        background_Z = Z == background_color
        
        logger.debug("%s %s", "Background color:", background_color)
        background_mask = background_Z.reshape(image_height, image_width, 3).all(axis=2)
        label_map[background_mask] = -1  # set background pixels to -1

    if show_plots:
        plt.figure(figsize=(8,8))
        plt.subplot(2,2,1)
        axis = plt.gca()
        plt.imshow(img)
        plt.title("Original Image")
        plt.axis('off')
        plt.subplot(2,2,2, sharex=axis, sharey=axis)
        plt.imshow(quant)
        plt.title("Quantized Image")
        plt.axis('off')
        plt.subplot(2,2,3, sharex=axis, sharey=axis)
        plt.imshow(label_map, cmap='tab10')
        plt.title("Label Map")
        plt.axis('off')

        plt.show()


    unique_colors, color_counts = np.unique(label_map, return_counts=True)



    # sort unique colors by count descending
    sort_idx = np.argsort(color_counts)[::-1]
    unique_colors = unique_colors[sort_idx]
    color_counts = color_counts[sort_idx]


    logger.debug("%s %s", "Total colors found:", len(unique_colors))
    logger.debug("%s %s", "Unique colors:", unique_colors)
    logger.debug("%s %s", "Color counts:", color_counts)


    total_pixels = image_height * image_width
    logger.debug("%s %s", "Total pixels:", total_pixels)



    valid_colors = unique_colors[color_counts > total_pixels * min_area]  # threshold can be adjusted
    logger.debug("%s %s", "Valid colors after removing small ones:", valid_colors)


    
    # reassign label_map to only keep valid colors, set others to their closest valid color that's physically next to them (instead of -1)

    for y in range(image_height):
        for x in range(image_width):
            if label_map[y, x] not in valid_colors:
                # check neighbors for valid colors
                neighbors = []
                if y > 0:
                    neighbors.append(label_map[y-1, x])
                if y < image_height - 1:
                    neighbors.append(label_map[y+1, x])
                if x > 0:
                    neighbors.append(label_map[y, x-1])
                if x < image_width - 1:
                    neighbors.append(label_map[y, x+1])

                neighbor_colors = [n for n in neighbors if n in valid_colors]
                if neighbor_colors:
                    label_map[y, x] = neighbor_colors[0]  # assign to first valid neighbor color
                else:
                    label_map[y, x] = -1  # if no valid neighbors, set to -1

    # if parts in the label map are only 1 pixel wide / high then assign them to the nearest valid color (instead of -1)

    for y in range(1, image_height -1):
        for x in range(1, image_width -1):
            current_color = label_map[y, x]
            too_thin_x = True
            too_thin_y = True
            if label_map[y-1, x] == current_color:
                too_thin_y = False
            if label_map[y+1, x] == current_color:
                too_thin_y = False
            if label_map[y, x-1] == current_color:
                too_thin_x = False
            if label_map[y, x+1] == current_color:
                too_thin_x = False
            
            if (too_thin_x or too_thin_y) and current_color in valid_colors:
                # check neighbors for valid colors
                neighbors = []
                if y > 0:
                    neighbors.append(label_map[y-1, x])
                if y < image_height - 1:
                    neighbors.append(label_map[y+1, x])
                if x > 0:
                    neighbors.append(label_map[y, x-1])
                if x < image_width - 1:
                    neighbors.append(label_map[y, x+1])

                neighbor_colors = [n for n in neighbors if n in valid_colors and n != current_color]
                if neighbor_colors:
                    label_map[y, x] = neighbor_colors[0]  # assign to first valid neighbor color
               

    unique_colors = np.unique(label_map)
    unique_colors = unique_colors[unique_colors != -1]  # remove background color if present

    if show_plots:
        plt.subplot(2,2,4, sharex=axis, sharey=axis)
        plt.imshow(label_map, cmap='tab10')
        plt.title("Cleaned Label Map")
        plt.axis('off')

        plt.show()


    max_colors = min(max_colors, len(unique_colors))

    logger.debug("%s %s", "Using colors:", unique_colors)
    logger.debug("%s %s", 'Max colors:', max_colors)


    # ----------------------------
    # PROCESS EACH COLOR
    # ----------------------------


    shapes = []

    if show_plots:
        plt.figure(figsize=(8,8))

        x_grid  = np.ceil(np.sqrt(max_colors)).astype(int)
        y_grid  = np.ceil(max_colors / x_grid).astype(int)

        logger.debug("%s %s %s %s", "Grid size for visualization:", x_grid, "x", y_grid)

    for cnum, color_id in enumerate(unique_colors):

        logger.debug(f"Processing color {color_id} ({cnum+1}/{len(unique_colors)})")

        mask = (label_map == color_id).astype(np.uint8)

        if show_plots:

            if cnum == 0:
                plt.subplot(y_grid, x_grid, cnum+1)
                axis = plt.gca()
            else:
                plt.subplot(y_grid, x_grid, cnum+1, sharex=axis, sharey=axis)
            plt.imshow(mask, cmap='gray')
            plt.title(f"Mask for Color {color_id}")
            # plt.axis('off')


        # --- split into connected components ---
        num_labels, labels_cc = cv2.connectedComponents(mask)

        for label_id in range(1, num_labels):

            component_mask = (labels_cc == label_id).astype(np.uint8)
            contours, hierarchy = cv2.findContours(
                component_mask,
                cv2.RETR_CCOMP,
                cv2.CHAIN_APPROX_SIMPLE
            )

            if hierarchy is None:
                continue

            hierarchy = hierarchy[0]

            for i, cnt in enumerate(contours):

                # only process outer contours
                if hierarchy[i][3] != -1:
                    continue

                outer = simplify(cnt, EPSILON_FACTOR)
                if outer is None:
                    continue

                holes = []
                hole_points = []

                # --- collect holes ---
                child = hierarchy[i][2]
                while child != -1:

                    hole = simplify(contours[child], EPSILON_FACTOR)

                    if hole is not None and len(hole) >= 3:
                        holes.append(hole)

                        # robust interior point
                        poly_hole = Polygon(hole)
                        hole_pt = poly_hole.representative_point().coords[0]
                        hole_points.append(hole_pt)

                    child = hierarchy[child][0]

                # --- build shapely polygon ---
                poly = Polygon(outer, holes if holes else None)

                if not poly.is_valid:
                    poly = poly.buffer(0)

                if poly.is_empty:
                    continue

                # extract cleaned geometry

                if not hasattr(poly, 'exterior') or poly.exterior is None:
                    logger.warning("Invalid polygon, skipping")
                    continue

                outer = np.array(poly.exterior.coords[:-1])
                holes = [np.array(r.coords[:-1]) for r in poly.interiors]

                outer = remove_collinear(outer)
                holes = [remove_collinear(h) for h in holes]

                # --- build triangle input ---
                vertices = []
                segments = []

                def add_ring(ring):
                    """Add ring."""
                    start = len(vertices)
                    vertices.extend(ring.tolist())
                    n = len(ring)
                    for j in range(n):
                        segments.append((start + j, start + (j+1) % n))

                add_ring(outer)

                hole_points = []
                for h in holes:
                    add_ring(h)
                    hole_pt = Polygon(h).representative_point().coords[0]
                    hole_points.append(hole_pt)

                A = dict(
                    vertices=np.array(vertices, dtype=float),
                    segments=np.array(segments)
                )

                if hole_points:
                    A["holes"] = np.array(hole_points)

                # --- triangulate ---
                try:
                    B = tr.triangulate(A, 'pq10')
                    # B = tr.triangulate(A, 'pq30')
                except Exception as e:
                    logger.warning("%s %s", "Triangle failed:", e)
                    continue

                if 'triangles' not in B:
                    continue

                verts = B['vertices']
                tris = B['triangles']
                # Store global arrays
                # all_vertices.extend(verts.tolist())

                trimmed_tris = []

                for t in tris:

                    # check that the triangle goes clockwise (positive area), if not flip it
                    tri_pts = verts[t]
                    tri_poly = Polygon(tri_pts)
                    if tri_poly.area < 0:

                        t[1], t[2] = t[2], t[1]
                    
                    trimmed_tris.append(t)

                verts = np.array(verts)
                trimmed_tris = np.array(trimmed_tris)

                # pts = approx.squeeze()
                pts = outer.astype(int)
                # Plot nicely
                color = quant[pts[0][1], pts[0][0]] / 255.000

                verts = verts / [image_width, image_height]  # normalize vertices to [0,1] range for VTK

                shapes.append((verts, trimmed_tris, color))

    # ----------------------------
    # FINAL PLOT
    # ----------------------------

    logger.debug("%s %s", "total shapes:", len(shapes))

    if show_plots:
        plt.figure(figsize=(8,8))



        colors = [s[2] for s in shapes]
        unique_colors = np.unique(colors, axis=0)
        logger.debug("%s %s", "Unique shape colors:", unique_colors)


        x_grid  = np.ceil(np.sqrt(len(unique_colors))).astype(int)
        y_grid  = np.ceil(len(unique_colors) / x_grid).astype(int)

        for cnum, color in enumerate(unique_colors):
            logger.debug(f"Color {cnum}: {color}")

            plt.subplot(y_grid, x_grid, cnum+1)
            plt.title(f"Shapes with color {color}")

            matching_shapes = [s for s in shapes if np.array_equal(s[2], color)]

            logger.debug(f"  Found {len(matching_shapes)} shapes with this color")

            for verts, tris, _ in matching_shapes:

                vertices = np.array(verts)
                triangles = np.array(tris)


                for t in triangles:
                    tri_pts = vertices[t] * [image_width, image_height]  # scale back to image size for plotting
                    polygon = plt.Polygon(tri_pts, facecolor=color, alpha=1.0)
                    plt.gca().add_patch(polygon)

                plt.xlim(0, image_width)
                plt.ylim(image_height, 0)
                plt.gca().set_aspect('equal')

        plt.figure(figsize=(8,8))
        plt.subplot(1,2,1)
        axis = plt.gca()
        plt.imshow(img)
        plt.title("Original Image")
        # plt.axis('off')
        plt.subplot(1,2,2, sharex=axis, sharey=axis)
        plt.title("Final Triangulated Shapes")

        for cnum, color in enumerate(unique_colors):

            matching_shapes = [s for s in shapes if np.array_equal(s[2], color)]

            for verts, tris, _ in matching_shapes:

                vertices = np.array(verts)
                triangles = np.array(tris)


                for t in triangles:
                    tri_pts = vertices[t] * [image_width, image_height]  # scale back to image size for plotting
                    polygon = plt.Polygon(tri_pts, facecolor=color, alpha=1.0)
                    plt.gca().add_patch(polygon)

                plt.xlim(0, image_width)
                plt.ylim(image_height, 0)
                plt.gca().set_aspect('equal')



        plt.show()


    return shapes



def convert_hex_color(hex_color):

    """Convert hex color."""
    ignore_prefixes = ['fill:', 'color:', 'stroke:', 'inline;', 'display:']

    for prefix in ignore_prefixes:
        hex_color = hex_color.replace(prefix, '')

    # hex_color = hex_color.strip('fill:')
    
    hex_color = hex_color.lstrip('#')
    hex_color = hex_color.split(';')[0]  # in case there are multiple style attributes, take the first one
    if len(hex_color) == 6:
        r, g, b = hex_color[:2], hex_color[2:4], hex_color[4:6]
        return (int(r, 16) / 255.0, int(g, 16) / 255.0, int(b, 16) / 255.0)
    elif len(hex_color) == 3:
        r, g, b = hex_color[0]*2, hex_color[1]*2, hex_color[2]*2
        return (int(r, 16) / 255.0, int(g, 16) / 255.0, int(b, 16) / 255.0)
    else:
        raise ValueError("Invalid hex color format", hex_color)
        logger.warning("%s %s", "Invalid hex color format, defaulting to black:", hex_color)

        random_color = np.random.rand(3)

        return (random_color[0], random_color[1], random_color[2])


def same_point(p1, p2, tol=1e-8):
    """Execute the same point operation."""
    return (
        np.isclose(p1[0], p2[0], atol=tol)
        and np.isclose(p1[1], p2[1], atol=tol)
    )


def add_point(boundary, pt):
    """
    Add point only if different from previous point.
    Returns index of point.
    """
    points = boundary["points"]

    if len(points) == 0 or not same_point(points[-1], pt):
        points.append(pt)

    return len(points) - 1


def sample_segment(seg, samples=3):
    """
    Convert SVG segment into sampled points.
    """
    if isinstance(seg, svgpathtools.Line):
        return [
            (seg.start.real, seg.start.imag),
            (seg.end.real, seg.end.imag),
        ]

    elif isinstance(
        seg,
        (
            svgpathtools.CubicBezier,
            svgpathtools.QuadraticBezier,
            svgpathtools.Arc,
        ),
    ):
        pts = []
        for t in np.linspace(0, 1, num=samples):
            pt = seg.point(t)
            pts.append((pt.real, pt.imag))
        return pts

    else:
        logger.debug("%s %s", "Unsupported segment type:", type(seg))
        return []
    

def polygon_area(points):
    """Execute the polygon area operation."""
    area = 0.0

    for i in range(len(points)):
        x1, y1 = points[i]
        x2, y2 = points[(i + 1) % len(points)]

        area += x1 * y2 - x2 * y1

    return area * 0.5


def mat_translate(tx, ty):
    """Execute the mat translate operation."""
    return np.array([
        [1, 0, tx],
        [0, 1, ty],
        [0, 0, 1]
    ], dtype=np.float64)


def mat_scale(sx, sy=None):

    """Execute the mat scale operation."""
    if sy is None:
        sy = sx

    return np.array([
        [sx, 0, 0],
        [0, sy, 0],
        [0, 0, 1]
    ], dtype=np.float64)


def mat_rotate(angle_deg):

    """Execute the mat rotate operation."""
    a = np.radians(angle_deg)

    c = np.cos(a)
    s = np.sin(a)

    return np.array([
        [c, -s, 0],
        [s,  c, 0],
        [0,  0, 1]
    ], dtype=np.float64)


def mat_matrix(a, b, c, d, e, f):

    """Execute the mat matrix operation."""
    return np.array([
        [a, c, e],
        [b, d, f],
        [0, 0, 1]
    ], dtype=np.float64)


def parse_svg_transform(transform_str):

    """Parse svg transform."""
    M = np.eye(3)

    pattern = r'(\w+)\(([^)]*)\)'

    matches = re.findall(pattern, transform_str)

    for cmd, values in matches:

        vals = [
            float(v)
            for v in re.split(r'[ ,]+', values.strip())
            if v
        ]

        if cmd == "translate":

            tx = vals[0]
            ty = vals[1] if len(vals) > 1 else 0.0

            T = mat_translate(tx, ty)

        elif cmd == "scale":

            sx = vals[0]
            sy = vals[1] if len(vals) > 1 else None

            T = mat_scale(sx, sy)

        elif cmd == "rotate":

            angle = vals[0]

            T = mat_rotate(angle)

        elif cmd == "matrix":

            T = mat_matrix(*vals)

        else:

            logger.debug("%s %s", "Unsupported transform:", cmd)

            continue

        # SVG applies transforms left-to-right
        M = M @ T

    return M

def apply_transform(pt, M):

    """Apply transform."""
    x, y = pt

    v = np.array([x, y, 1.0])

    r = M @ v

    return (r[0], r[1])

def svg_fill_rule(attributes):
    """``"nonzero"`` (SVG's default) or ``"evenodd"`` for a path's attributes."""
    rule = attributes.get("fill-rule")
    match = re.search(r"fill-rule\s*:\s*([a-z]+)", attributes.get("style", ""))
    if match:
        rule = match.group(1)
    return "evenodd" if str(rule).strip().lower() == "evenodd" else "nonzero"


def hole_points(boundaries, fill_rule="nonzero"):
    """One point inside each unfilled region of a path of closed *boundaries*.

    Follows SVG's fill rules rather than reading every clockwise boundary as
    a hole (which dropped paths whose separate shapes were all drawn
    clockwise): the region just inside each boundary -- outside the
    boundaries nested directly in it -- has a winding number, the sum of the
    directions (+1 / -1) of the boundaries around it. It is unfilled when
    that number is zero (``nonzero``, the SVG default) or even
    (``evenodd``). Each point is placed in that region, not in an island
    nested inside it, so the triangulator removes exactly the unfilled part.
    """
    polygons, directions = [], []
    for points in boundaries:
        polygon = Polygon(points) if len(points) >= 3 else Polygon()
        polygons.append(polygon if polygon.is_valid else polygon.buffer(0))
        directions.append(1 if len(points) >= 3 and polygon_area(points) > 0 else -1)
    inner_points = [None if polygon.is_empty else polygon.representative_point()
                    for polygon in polygons]

    def encloses(j, i):
        return (j != i and not polygons[j].is_empty and
                polygons[j].area > polygons[i].area and
                polygons[j].contains(inner_points[i]))

    depths = [None if polygon.is_empty else
              sum(1 for j in range(len(polygons)) if encloses(j, i))
              for i, polygon in enumerate(polygons)]
    holes = []
    for i, polygon in enumerate(polygons):
        if depths[i] is None:
            continue
        region = polygon
        for j in range(len(polygons)):
            if depths[j] == depths[i] + 1 and encloses(i, j):
                region = region.difference(polygons[j])
        if region.is_empty:
            continue
        point = region.representative_point()
        winding = sum(directions[j] for j in range(len(polygons))
                      if not polygons[j].is_empty and polygons[j].contains(point))
        unfilled = winding % 2 == 0 if fill_rule == "evenodd" else winding == 0
        if unfilled:
            holes.append(point.coords[0])
    return holes


def convert_svg_to_triangles(svg_path_str, invert_y=True, plot=False, normalize=True, triangulate_opts='pq10', arc_resolution=5):

    """Convert svg to triangles."""
    paths, attributes = svgpathtools.svg2paths(svg_path_str)



    if plot:
        plt.figure(figsize=(8,8))


    shapes = []

    # bounds_string = svgpathtools.svg2paths(svg_path_str, return_svg_attributes=True)[2]['viewBox']
    # # print("SVG bounds:", bounds_string)
    # split_string = [float(s) for s in bounds_string.split()]
    # bounds = [split_string[0], split_string[2], split_string[1], split_string[3]]



    for pnum, path in enumerate(paths):

        all_boundaries = []

        logger.debug(f"\nProcessing path {pnum} with {len(path)} segments")

        current_boundary = {
            "points": [],
            "segments": [],
        }

        previous_end = None

        transform = attributes[pnum].get("transform")

        if transform:
            tf = parse_svg_transform(transform)

        for seg in path:


            sampled_pts = sample_segment(seg, arc_resolution)

            if transform:

            
                sampled_pts = [apply_transform(pt, tf) for pt in sampled_pts]


            if len(sampled_pts) == 0:
                continue

            start_pt = sampled_pts[0]

            # --------------------------------------------------
            # Detect discontinuity -> start new boundary
            # --------------------------------------------------
            if previous_end is not None:
                if not same_point(previous_end, start_pt):

                    # Save old boundary if non-empty
                    if len(current_boundary["points"]) > 0:
                        all_boundaries.append(current_boundary)

                    # Start new boundary
                    current_boundary = {
                        "points": [],
                        "segments": [],
                    }


            # --------------------------------------------------
            # Add sampled points + segments
            # --------------------------------------------------
            prev_idx = None

            for pt in sampled_pts:

                idx = add_point(current_boundary, pt)

                if prev_idx is not None and idx != prev_idx:
                    current_boundary["segments"].append((prev_idx, idx))

                prev_idx = idx

            previous_end = sampled_pts[-1]

        # Save final boundary
        if len(current_boundary["points"]) > 0:
            all_boundaries.append(current_boundary)


        fill_color = attributes[pnum].get('style', '#000000')
        color = convert_hex_color(fill_color)

        vertices = []
        segments = []
        holes = hole_points([boundary["points"] for boundary in all_boundaries],
                            svg_fill_rule(attributes[pnum]))

        vertex_offset = 0

        for boundary in all_boundaries:

            pts = boundary["points"]

            # add vertices
            vertices.extend(pts)

            # add segments with offset
            for s in boundary["segments"]:
                segments.append((
                    s[0] + vertex_offset,
                    s[1] + vertex_offset
                ))

            # close the loop if needed
            if len(pts) > 2:
                segments.append((
                    vertex_offset + len(pts) - 1,
                    vertex_offset
                ))

            vertex_offset += len(pts)

        vertices = np.array(vertices, dtype=np.float64)
        segments = np.array(segments, dtype=np.int32)




        # check for duplicate vertices and remove them
        for i in range(len(vertices)):
            for j in range(i+1, len(vertices)):
                if j >= len(vertices):
                    continue
                if same_point(vertices[i], vertices[j]):
                    segments[segments == j] = i  # redirect segments to the first vertex
                    
                    # delete the duplicate vertex
                    vertices = np.delete(vertices, j, axis=0)
                    segments[segments > j] -= 1  # adjust segment indices after deletion


        A = {
            "vertices": vertices,
            "segments": segments,
        }
        if len(all_boundaries) > 1:
            if len(holes) > 0:
                A["holes"] = np.array(holes)

        logger.debug("%s %s %s %s", "Triangulating path with", len(vertices), "points and color", color)


        # plt.figure(figsize=(12,6))
        # plt.subplot(1,2,1)
        # plt.plot(vertices[:, 0], vertices[:, 1], 'o-')
        # plt.title(f"Original Path with {len(vertices)} points")
        # plt.axis('equal')
        # # plt.show()


        B = tr.triangulate(A, triangulate_opts)

        # # plt.plot(points[:, 0], points[:, 1], 'o-')
        # plt.subplot(1,2,2)
        # for t in B['triangles']:
        #     tri_pts = B['vertices'][t]
        #     polygon = plt.Polygon(tri_pts, facecolor=color, alpha=0.5)
        #     plt.gca().add_patch(polygon)

        # plt.title(f"Triangulated Path with {len(B['triangles'])} triangles")
        # plt.axis('equal')
        # plt.show()

        # if plot:
        #     # plt.plot(points[:, 0], points[:, 1], 'o-')
        #     for t in B['triangles']:
        #         tri_pts = B['vertices'][t]
        #         polygon = plt.Polygon(tri_pts, facecolor=color, alpha=0.5)
        #         plt.gca().add_patch(polygon)


        if 'triangles' not in B:
            logger.warning("Triangulation failed, skipping this path")
            continue

        logger.debug("%s %s %s", "Triangulated to", len(B['triangles']), "triangles")


        verts = B['vertices']
        tris = B['triangles']
        # if normalize:
        #     verts = (verts - bounds[0]) / (bounds[1] - bounds[0])  # normalize to [0,1] range




        logger.debug("%s %s %s", 'verts range:', np.min(verts, axis=0), np.max(verts, axis=0))

        if plot:
            for t in tris:
                tri_pts = verts[t]
                polygon = plt.Polygon(tri_pts, facecolor=color, alpha=0.5)
                plt.gca().add_patch(polygon)


        shapes.append((verts, tris, color))


    keep_aspect_ratio = True

    if normalize:
        all_verts = np.concatenate([s[0] for s in shapes], axis=0)
        min_xy = np.min(all_verts, axis=0)
        max_xy = np.max(all_verts, axis=0)

        logger.debug("%s %s %s", "Overall vertex bounds:", min_xy, max_xy)

        if keep_aspect_ratio:

            # determine aspect ratio and add padding to the shorter dimension so that the final normalized shapes fit in a square without distortion


            width = max_xy[0] - min_xy[0]
            height = max_xy[1] - min_xy[1]
            if width > height:
                padding = (width - height) / 2
                min_xy[1] -= padding
                max_xy[1] += padding
            else:
                padding = (height - width) / 2
                min_xy[0] -= padding
                max_xy[0] += padding


        for i in range(len(shapes)):
            verts, tris, color = shapes[i]
            verts = (verts - min_xy) / (max_xy - min_xy)  # normalize to [0,1] range
            shapes[i] = (verts, tris, color)


    if invert_y:
        vertices[:, 1] = 1- vertices[:, 1]


    for i, shape in enumerate(shapes):
        verts, tris, color = shape
        logger.debug(f"Shape {i}: {len(verts)} vertices, {len(tris)} triangles, color {color}")

           


    if plot:
        plt.title("SVG Paths")
        plt.axis('equal')
        plt.gca().invert_yaxis()  # SVG coordinate system has y going down, so invert for plotting
        plt.show()


    return shapes


def convert_shapes_to_polydata(shapes, scale=1, join=True, use_assembly=False, verbose=False):

    """Convert shapes to polydata."""
    all_vertices = [verts for verts, _, _ in shapes]
    all_triangles = []
    triangle_colors = []

    vertex_offset = 0

    for verts, tris, color in shapes:
        all_triangles.append(tris + vertex_offset)
        triangle_colors.append(np.tile(color, (len(tris), 1)))
        vertex_offset += len(verts)

    if join:

        if use_assembly:

            assembly = vtk.vtkAssembly()

            for verts, tris, color in shapes:

                polydata = vtk.vtkPolyData()

                points = vtk.vtkPoints()
                for v in verts:
                    points.InsertNextPoint(v[0] * scale, v[1] * scale, 0.0)  # z=0 for 2D

                polys = vtk.vtkCellArray()
                for t in tris:
                    polys.InsertNextCell(3, t)  # 3 vertices per triangle

                colors = vtk.vtkUnsignedCharArray()
                colors.SetNumberOfComponents(4)
                colors.SetName("Colors")
                rgba = (color * 255).astype(np.uint8)
                for _ in range(len(tris)):
                    colors.InsertNextTuple4(rgba[0], rgba[1], rgba[2], rgba[3] if len(rgba) > 3 else 255)

                polydata.SetPoints(points)
                polydata.SetPolys(polys)
                polydata.GetCellData().SetScalars(colors)

                mapper = vtk.vtkPolyDataMapper()
                mapper.SetInputData(polydata)

                actor = vtk.vtkActor()
                actor.SetMapper(mapper)

                assembly.AddPart(actor)

            return assembly


        all_vertices = np.vstack(all_vertices)
        all_triangles = np.vstack(all_triangles)
        triangle_colors = np.vstack(triangle_colors)

        # Create VTK PolyData
        polydata = vtk.vtkPolyData()

        points = vtk.vtkPoints()
        for v in all_vertices:
            points.InsertNextPoint(v[0] * scale, v[1] * scale, 0.0)  # z=0 for 2D

        polys = vtk.vtkCellArray()
        for t in all_triangles:
            polys.InsertNextCell(3, t)  # 3 vertices per triangle

        colors = vtk.vtkUnsignedCharArray()
        colors.SetNumberOfComponents(4)
        colors.SetName("Colors")
        for c in triangle_colors:
            rgba = (c * 255).astype(np.uint8)
            colors.InsertNextTuple4(rgba[0], rgba[1], rgba[2], rgba[3] if len(rgba) > 3 else 255)

        polydata.SetPoints(points)
        polydata.SetPolys(polys)
        polydata.GetCellData().SetScalars(colors)

        return polydata

    else:

        polydata_list = []

        for i, (verts, tris, color) in enumerate(shapes):

            polydata = vtk.vtkPolyData()

            points = vtk.vtkPoints()
            for v in verts:
                points.InsertNextPoint(v[0] * scale, v[1] * scale, 0.0)  # z=0 for 2D

            polys = vtk.vtkCellArray()
            for t in tris:
                polys.InsertNextCell(3, t)  # 3 vertices per triangle

            colors = vtk.vtkUnsignedCharArray()
            colors.SetNumberOfComponents(4)
            colors.SetName("Colors")
            rgba = (color * 255).astype(np.uint8)
            for _ in range(len(tris)):
                colors.InsertNextTuple4(rgba[0], rgba[1], rgba[2], rgba[3] if len(rgba) > 3 else 255)

            polydata.SetPoints(points)
            polydata.SetPolys(polys)
            polydata.GetCellData().SetScalars(colors)

            polydata_list.append(polydata)

        return polydata_list



def save_shapes_as_polydata(shapes, filename, invert_y=True):
    # with open(filename, "w") as f:
    #     for verts, tris, color in shapes:
    #         f.write(f"# Shape with color: {color}\n")
    #         f.write("# Vertices\n")
    #         for v in verts:
    #             f.write(f"{v[0]} {v[1]}\n")
    #         f.write("# Triangles\n")
    #         for t in tris:
    #             f.write(f"{t[0]} {t[1]} {t[2]}\n")
    #         f.write("\n")

    """Save shapes as polydata."""
    if invert_y:
        for i in range(len(shapes)):
            verts, tris, color = shapes[i]
            verts[:, 1] = 1.0 - verts[:, 1]  # invert y coordinate
            shapes[i] = (verts, tris, color)

    writer = vtk.vtkPolyDataWriter()
    writer.SetFileName(filename)
    polydata = convert_shapes_to_polydata(shapes)
    writer.SetInputData(polydata)
    writer.Write()


# def save_shapes_as_svg(shapes, filename):
    # with open(filename, "w") as f:
    #     f.write('<svg xmlns="http://www.w3.org/2000/svg" version="1.1">\n')

    #     for verts, tris, color in shapes:
    #         hex_color = '#%02x%02x%02x' % tuple((color * 255).astype(int))
    #         f.write(f'<g fill="{hex_color}" stroke="none">\n')
    #         for t in tris:
    #             tri_pts = verts[t]
    #             points_str = " ".join([f"{p[0]},{p[1]}" for p in tri_pts])
    #             f.write(f'<polygon points="{points_str}" />\n')
    #         f.write('</g>\n')

    #     f.write('</svg>\n')

def read_vtk_icon_file(filepath):
    

    """Read vtk icon file."""
    reader = vtk.vtkPolyDataReader()
    reader.SetFileName(filepath)
    reader.Update()
    polydata = reader.GetOutput()

    return polydata

if __name__ == "__main__":

    import os
    import sys

    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    import vtk
    from . import widgets

    svg_path = sys.argv[1] if len(sys.argv) > 1 else None

    # shapes = convert_svg_to_triangles(svg_path, eps_factor=0.001, plot=False, normalize=True, triangulate_opts='pq10')
    # shapes = convert_image_to_triangles(IMAGE_PATH, show_plots=True)

    # shapes = convert_image_to_triangles(IMAGE_PATH, max_colors=MAX_COLORS, show_plots=False)

    # for shape in shapes:
    #     verts, tris, color = shape


    # lets see if we can convert every .png icon in the GUI/icons folder to triangles and display them in VTK using the VectorButtonWidget



    folder_path = os.path.join(os.path.dirname(__file__), "icons", "svg_icons")

    file_list = sorted(os.listdir(folder_path))

    converted_shapes = {}

    for filename in tqdm(file_list):
        print(f"Converting {filename}")
        if filename.endswith(".png"):
            image_path = os.path.join(folder_path, filename)
            print(f"\nProcessing icon: {filename}")
            shapes = convert_image_to_triangles(image_path, max_colors=MAX_COLORS, show_plots=False)
            converted_shapes[filename] = shapes
            print(f"Converted {filename} to {len(shapes)} shapes")
        elif filename.endswith(".svg"):
            image_path = os.path.join(folder_path, filename)
            print(f"\nProcessing icon: {filename}")
            shapes = convert_svg_to_triangles(image_path, plot=False, triangulate_opts='pq10')
            converted_shapes[filename] = shapes
            print(f"Converted {filename} to {len(shapes)} shapes")
        elif filename.endswith(".pdf"):
            print(f"Skipping PDF icon (not supported yet): {filename}")
        elif filename.endswith(".ico"):
            print(f"Skipping ICO icon (not supported yet): {filename}")
        elif filename.endswith(".vtk"):
            shapes = read_vtk_icon_file(os.path.join(folder_path, filename))
            converted_shapes[filename] = shapes

            continue
        
        else:
            continue

        basename = os.path.splitext(filename)[0]

        pd_name = f"{basename}.vtk"

        # one above the folderpath

        mother_folder = os.path.dirname(folder_path)

        pd_filepath = os.path.join(mother_folder,'vtk_icons', pd_name)

        save_shapes_as_polydata(shapes, pd_filepath)

    ren = vtk.vtkRenderer()
    renWin = vtk.vtkRenderWindow()
    renWin.AddRenderer(ren)
    iren = vtk.vtkRenderWindowInteractor()
    iren.SetRenderWindow(renWin)

    iren.SetInteractorStyle(vtk.vtkInteractorStyleTrackballCamera())
    # simple 3D object
    sphere = vtk.vtkSphereSource()
    mapper = vtk.vtkPolyDataMapper()
    mapper.SetInputConnection(sphere.GetOutputPort())
    actor = vtk.vtkActor()
    actor.SetMapper(mapper)
    ren.AddActor(actor)




    def on_button(widget, ev=None):
        """Handle button."""
        print("Clicked! State:", widget.state)



    grid_x = int(np.ceil(np.sqrt(len(converted_shapes))))
    grid_y = int(np.ceil(len(converted_shapes) / grid_x))

    step_x = 1.0 / grid_x
    step_y = 1.0 / grid_y



    print("Grid size for VTK buttons:", grid_x, "x", grid_y)

    for i, (filename, shapes) in enumerate(converted_shapes.items()):


        grid_x_pos = (i % grid_x) * step_x
        grid_y_pos = (i // grid_x) * step_y

        button = widgets.VectorButtonWidget(
            ren, iren,
            input_data=shapes,
            callback=on_button,
            bounds=(grid_x_pos, grid_x_pos + step_x, grid_y_pos, grid_y_pos + step_y),
            color=None
        )



    # for i in range(100):

    #     rand_x = (np.random.rand() * 0.9) + 0.05
    #     rand_y = (np.random.rand() * 0.9) + 0.05

    #     button = widgets.VectorButtonWidget(
    #         ren, iren,
    #         shapes=shapes,
    #         callback=on_button,
    #         bounds=(rand_x, rand_x+0.05, rand_y, rand_y + 0.05),
    #         color=(0.1, 0.6, 1.0)
    #     )

    renWin.SetSize(800, 600)
    ren.SetBackground(0.1, 0.1, 0.1)

    # set polygon edge smoothing in the renderer for better appearance

    ren.GetRenderWindow().SetMultiSamples(4)  # enable anti-aliasing
    ren.GetRenderWindow().SetAlphaBitPlanes(1)  # enable alpha channel for smoother edges
    ren.SetUseDepthPeeling(1)  # enable depth peeling for proper transparency
    ren.SetMaximumNumberOfPeels(100)  # increase max peels for complex scenes
    ren.SetOcclusionRatio(0.1)  # lower occlusion ratio for

    renWin.Render()
    iren.Initialize()
    iren.Start()
