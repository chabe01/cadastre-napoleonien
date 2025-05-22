import geopandas as gpd
import pandas as pd
import numpy as np
import os
import shapely.affinity
from shapely.geometry import mapping, shape
from scipy.linalg import lstsq

# === 1. Charger les GCPs depuis le fichier QGIS .points ===
def read_gcps(filepath):
    src_pts = []
    dst_pts = []
    with open(filepath, 'r') as f:
        for line in f:
            if line.startswith('#') or line.startswith('mapX') or not line.strip():
                continue
            parts = line.strip().split(',')
            dst_x, dst_y = float(parts[0]), float(parts[1])  # mapX, mapY (WGS84)
            src_x, src_y = float(parts[2]), float(parts[3])  # sourceX, sourceY
            src_pts.append([src_x, src_y])
            dst_pts.append([dst_x, dst_y])
    return np.array(src_pts), np.array(dst_pts)

# === 2. Calculer la matrice de transformation affine ===
def compute_affine(src, dst):
    A = []
    B = []
    for (x, y), (x_, y_) in zip(src, dst):
        A.append([x, y, 1, 0, 0, 0])
        A.append([0, 0, 0, x, y, 1])
        B.append(x_)
        B.append(y_)
    A = np.array(A)
    B = np.array(B)
    params, _, _, _ = lstsq(A, B)  # Résolution des moindres carrés
    return params  # a, b, c, d, e, f

# === 3. Appliquer la transformation à chaque géométrie ===
def transform_geometry(geom, params):
    a, b, c, d, e, f = params
    return shapely.affinity.affine_transform(geom, [a, b, d, e, c, f])

# === 4. Charger le vecteur, transformer, sauvegarder ===
def georeference_vector(gpkg_path, layer_name, points_path, output_path, epsg=4326):
    src, dst = read_gcps(points_path)
    params = compute_affine(src, dst)

    gdf = gpd.read_file(gpkg_path, layer=layer_name)
    gdf['geometry'] = gdf['geometry'].apply(lambda geom: transform_geometry(geom, params))

    gdf.set_crs(epsg=epsg, inplace=True, allow_override=True)  # ou EPSG:2154 selon ton cas
    gdf.to_file(output_path, layer=layer_name, driver="GPKG")
    print("Transformation terminée et fichier sauvegardé :", output_path)

# === 5. Fusion de couches ===

def merge_layers(gpkg_paths, layer_name, output_path):
    liste_gdf = []
    for gpkg_path in gpkg_paths:
        gdf = gpd.read_file(gpkg_path, layer=layer_name)
        liste_gdf.append(gdf)

    merged_gdf = gpd.GeoDataFrame(pd.concat(liste_gdf, ignore_index=True), crs=liste_gdf[0].crs)
    merged_gdf.to_file(output_path, layer=layer_name, driver="GPKG")
    print("Fusion terminée et fichier sauvegardé :", output_path)

# === 6. Exécution ===

out_epsg = 2154
gcp_folder = "./gcp"
in_vectors_folder = "./vecteurs/in"
out_vectors_folder = "./vecteurs/out"
in_rasters_folder = "./rasters/in"
parcels_layer_name = "parcelles"
buildings_layer_name = "batiments"
sections = ["A1", "A2", "B1", "B2", "C1", "C2", "D1", "D2"]

# Créer le dossier s'il n'existe pas
os.makedirs(out_vectors_folder, exist_ok=True)

# Géoréférencer les vecteurs issues de la numérisation des rasters qui ont été géoréférencés et dont les paramètres sont fournis par les GCPs
for section in sections:
    georeference_vector(
        gpkg_path=f"{in_vectors_folder}/{section}.gpkg",
        layer_name=parcels_layer_name,
        points_path=f"{gcp_folder}/{section}.jpg.points",
        output_path=f"{out_vectors_folder}/epsg_{out_epsg}_{section}_{parcels_layer_name}.gpkg",
        epsg=out_epsg
    )

    georeference_vector(
        gpkg_path=f"{in_vectors_folder}/{section}.gpkg",
        layer_name=buildings_layer_name,
        points_path=f"{gcp_folder}/{section}.jpg.points",
        output_path=f"{out_vectors_folder}/epsg_{out_epsg}_{section}_{buildings_layer_name}.gpkg",
        epsg=out_epsg
    )

# Fusionner les couches géoréférencées
gpkg_paths = [f"{out_vectors_folder}/epsg_{out_epsg}_{section}_{parcels_layer_name}.gpkg" for section in sections]
merge_layers(
    gpkg_paths=gpkg_paths,
    layer_name=parcels_layer_name,
    output_path=f"{out_vectors_folder}/epsg_{out_epsg}_{parcels_layer_name}_merged.gpkg"
)
gpkg_paths = [f"{out_vectors_folder}/epsg_{out_epsg}_{section}_{buildings_layer_name}.gpkg" for section in sections]
merge_layers(
    gpkg_paths=gpkg_paths,
    layer_name=buildings_layer_name,
    output_path=f"{out_vectors_folder}/epsg_{out_epsg}_{buildings_layer_name}_merged.gpkg"
)


# georeference_vector(
#     gpkg_path="./vecteurs/C2.gpkg",
#     layer_name="parcelles",
#     points_path="./gcp/C2.jpg.points",
#     output_path="./vecteurs/epsg_{epsg}_C2.gpkg"
# )

