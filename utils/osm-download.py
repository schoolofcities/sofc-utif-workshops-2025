# Downloading OpenStreetMap (OSM) road network data and water areas/lines via Overpass

import requests
import geopandas as gpd
from shapely.geometry import box

input_region_polygon = "../dehradun-psi/DEHRADUN.geojson"
output_file_roads = "../dehradun-psi/OSM-roads.gpkg"
output_file_water = "../dehradun-psi/OSM-water.gpkg"

# Load GeoJSON and extract bounding box using GeoPandas
def get_bbox_from_geojson(file_path):
	bounds_extension = 0.08 # go beyond the exact bounding box, for some overflow of data
	gdf = gpd.read_file(file_path)
	minx, miny, maxx, maxy = gdf.total_bounds  # Get bounding box [min_lon, min_lat, max_lon, max_lat]
	return [miny - bounds_extension, minx - bounds_extension, maxy + bounds_extension, maxx + bounds_extension], box(minx - bounds_extension, miny - bounds_extension, maxx + bounds_extension, maxy + bounds_extension)  # Overpass bbox + Shapely bbox geometry
# Specify your local GeoJSON file
bbox, bbox_polygon = get_bbox_from_geojson(input_region_polygon)

# Overpass API URL
url = "https://overpass-api.de/api/interpreter"



# Overpass QL query to get all ways with highway=* within the bounding box
query_roads = f"""
[out:json];
way["highway"]({bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]});
(._;>;);
out qt;
"""

# Send the request
response = requests.get(url, params={"data": query_roads})

# Process response
if response.status_code == 200:
	data = response.json()

	# Extract nodes for coordinate mapping
	nodes = {el["id"]: (el["lon"], el["lat"]) for el in data["elements"] if el["type"] == "node"}

	# Convert Overpass JSON to GeoDataFrame
	highways = []
	for element in data["elements"]:
		if element["type"] == "way" and "nodes" in element:
			coords = [nodes[node_id] for node_id in element["nodes"] if node_id in nodes]
			properties = element.get("tags", {})
			
			# Keep only "highway" and "name" attributes
			filtered_properties = {
				"highway": properties.get("highway", None),
				"name": properties.get("name", None)
			}

			highways.append({
				"geometry": {"type": "LineString", "coordinates": coords},
				"properties": filtered_properties
			})

	# Create a GeoDataFrame
	gdf_highways = gpd.GeoDataFrame.from_features(highways, crs="EPSG:4326")
	
	# Clip to bounding box polygon
	gdf_clipped = gpd.clip(gdf_highways, bbox_polygon)

	# Save to GPKG file
	gdf_clipped.to_file(output_file_roads, driver="GPKG")

	print(f"Saved road data to {output_file_roads}")

else:
	print("Error:", response.status_code, response.text)



query_water = f"""
[out:json];
(
  way["waterway"]({bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]});
  way["natural"="water"]({bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]});
  relation["natural"="water"]({bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]});
);
(._;>;);
out qt;
"""

# Send the request
response = requests.get(url, params={"data": query_water})

# Process response
if response.status_code == 200:
    data = response.json()

    # Extract nodes for coordinate mapping
    nodes = {el["id"]: (el["lon"], el["lat"]) for el in data["elements"] if el["type"] == "node"}

    # Convert Overpass JSON to GeoDataFrame
    features = []
    for element in data["elements"]:
        if element["type"] == "way" and "nodes" in element:
            coords = [nodes[node_id] for node_id in element["nodes"] if node_id in nodes]
            geom_type = "LineString" if "waterway" in element.get("tags", {}) else "Polygon"

            features.append({
                "geometry": {"type": geom_type, "coordinates": [coords]},
                "properties": {}  # Remove all attributes
            })

    # Create a GeoDataFrame
    gdf = gpd.GeoDataFrame.from_features(features, crs="EPSG:4326")

    # Clip to bounding box
    gdf_clipped = gpd.clip(gdf, bbox_polygon)

    # Save to GPKG
    gdf_clipped.to_file(output_file_water, driver="GPKG", layer="water")

    print(f"Saved water data to {output_file_water}")

else:
    print("Error:", response.status_code, response.text)