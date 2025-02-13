import requests
import geopandas as gpd
from shapely.geometry import box, Point, LineString, Polygon, MultiPolygon


input_region_polygon = "../dehradun-psi/DEHRADUN.geojson"
output_file_roads = "../dehradun-psi/OSM-roads.gpkg"
output_file_water = "../dehradun-psi/OSM-water.gpkg"


def get_bbox_from_geojson(file_path):
	bounds_extension = 0.08 # go beyond the exact bounding box, for some overflow of data
	gdf = gpd.read_file(file_path)
	minx, miny, maxx, maxy = gdf.total_bounds  # Get bounding box [min_lon, min_lat, max_lon, max_lat]
	return [miny - bounds_extension, minx - bounds_extension, maxy + bounds_extension, maxx + bounds_extension], box(minx - bounds_extension, miny - bounds_extension, maxx + bounds_extension, maxy + bounds_extension)  # Overpass bbox + Shapely bbox geometry

bbox, bbox_polygon = get_bbox_from_geojson(input_region_polygon)



def fetch_osm_data(query, properties_to_keep=None, geometry_type="line", output_file="output.gpkg"):
    """
    Fetches data from Overpass API, processes it into a GeoDataFrame, and saves it as a GeoPackage.

    Parameters:
        query (str): Overpass QL query to fetch data.
        properties_to_keep (list): List of tags to retain in the output.
        geometry_type (str): Expected geometry type - "point", "line", or "polygon".
        output_file (str): Name of the output GeoPackage file.

    Returns:
        None (saves data to a GPKG file).
    """
    # Overpass API endpoint
    url = "https://overpass-api.de/api/interpreter"
    response = requests.get(url, params={"data": query})

    if response.status_code != 200:
        print("Error:", response.status_code, response.text)
        return

    data = response.json()

    # Extract nodes for coordinate mapping
    nodes = {el["id"]: (el["lon"], el["lat"]) for el in data["elements"] if el["type"] == "node"}

    # Process elements into features
    features = []
    for element in data["elements"]:
        geom = None

        if element["type"] == "node" and geometry_type == "point":
            geom = Point(nodes[element["id"]]) if element["id"] in nodes else None
        elif element["type"] == "way" and "nodes" in element:
            coords = [nodes[node_id] for node_id in element["nodes"] if node_id in nodes]
            if coords:
                geom = LineString(coords) if geometry_type == "line" else Polygon([coords])
        elif element["type"] == "relation" and geometry_type == "polygon":
            coords = [[nodes[node_id] for node_id in member["ref"]] for member in element.get("members", []) if member["type"] == "way" and member["ref"] in nodes]
            if coords:
                geom = MultiPolygon([Polygon(c) for c in coords if len(c) >= 3]) if coords else None

        if geom and not geom.is_empty:
            # Extract properties as separate columns
            properties = element.get("tags", {}) if properties_to_keep else {}
            filtered_properties = {prop: properties.get(prop, None) for prop in properties_to_keep} if properties_to_keep else {}

            # Append feature
            features.append({"geometry": geom, **filtered_properties})

    # Ensure non-empty GeoDataFrame
    if not features:
        print("No valid geometries found.")
        return

    # Create GeoDataFrame
    gdf = gpd.GeoDataFrame(features, crs="EPSG:4326")

    # Save to GeoPackage
    gdf.to_file(output_file, driver="GPKG")

    print(f"Saved data to {output_file}")



query_roads = f"""
[out:json];
way["highway"]({bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]});
(._;>;);
out qt;
"""

fetch_osm_data(query_roads, properties_to_keep=["highway", "name"], geometry_type="line", output_file=output_file_roads)