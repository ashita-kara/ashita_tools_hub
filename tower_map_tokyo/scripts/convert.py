import xml.etree.ElementTree as ET
import json
import os
import zipfile

def kml_color_to_css_color(kml_color_str):
    """
    KMLの色(aabbggrr)をCSSの色(#rrggbb)に変換する
    KMLは Alpha, Blue, Green, Red の順で並んでいるため並べ替えが必要
    """
    if not kml_color_str or len(kml_color_str) < 8:
        return "#0000ff" # デフォルト青

    # aabbggrr -> bb=2:4, gg=4:6, rr=6:8
    # CSSは #rrggbb
    blue = kml_color_str[2:4]
    green = kml_color_str[4:6]
    red = kml_color_str[6:8]
    
    return f"#{red}{green}{blue}"

def convert_kml_to_geojson_with_style():
    input_file = 'mymap.kml'
    output_file = 'mymap.geojson'
    
    if not os.path.exists(input_file):
        print(f"エラー: {input_file} が見つかりません。")
        return

    print(f"[{input_file}] の解析を開始します（色情報付き）...")

    try:
        tree = ET.parse(input_file)
        root = tree.getroot()
        
        # 名前空間の定義
        ns = {'kml': 'http://www.opengis.net/kml/2.2'}
        
        # 1. スタイル(IDと色の対応表)を作成する
        style_map = {}
        for style in root.findall('.//kml:Style', ns):
            style_id = style.get('id')
            if not style_id:
                continue
            
            # アイコンの色 (ピン)
            icon_style = style.find('kml:IconStyle/kml:color', ns)
            # 線の色 (ルート、エリアの枠)
            line_style = style.find('kml:LineStyle/kml:color', ns)
            # 面の色 (エリアの塗りつぶし)
            poly_style = style.find('kml:PolyStyle/kml:color', ns)
            
            color = None
            if icon_style is not None:
                color = kml_color_to_css_color(icon_style.text)
            elif line_style is not None:
                color = kml_color_to_css_color(line_style.text)
            elif poly_style is not None:
                color = kml_color_to_css_color(poly_style.text)
            
            if color:
                style_map[f"#{style_id}"] = color

        # スタイルマップ（StyleMap）の解決（normal状態の色を採用）
        for style_map_def in root.findall('.//kml:StyleMap', ns):
            map_id = style_map_def.get('id')
            for pair in style_map_def.findall('kml:Pair', ns):
                key = pair.find('kml:key', ns)
                style_url = pair.find('kml:styleUrl', ns)
                if key is not None and key.text == 'normal' and style_url is not None:
                    # 参照先のスタイルIDから色を取得
                    target_style = style_url.text
                    if target_style in style_map:
                        style_map[f"#{map_id}"] = style_map[target_style]

        features = []

        # 2. Placemarkの解析
        for placemark in root.findall('.//kml:Placemark', ns):
            name = placemark.find('kml:name', ns)
            name_text = name.text if name is not None else "名称なし"
            
            description = placemark.find('kml:description', ns)
            desc_text = description.text if description is not None else ""
            
            # スタイルの取得
            style_url = placemark.find('kml:styleUrl', ns)
            marker_color = "#007bff" # デフォルト
            if style_url is not None and style_url.text in style_map:
                marker_color = style_map[style_url.text]

            # ジオメトリ（形状）を探す
            geometry = None
            
            # Point
            point = placemark.find('kml:Point', ns)
            if point is not None:
                coords_text = point.find('kml:coordinates', ns).text
                coords = [float(x) for x in coords_text.strip().split(',')]
                # MyMapsは lng, lat, alt
                geometry = {"type": "Point", "coordinates": [coords[0], coords[1]]}

            # LineString
            line = placemark.find('kml:LineString', ns)
            if line is not None:
                coords_text = line.find('kml:coordinates', ns).text
                coords = []
                for c in coords_text.strip().split():
                    parts = c.split(',')
                    coords.append([float(parts[0]), float(parts[1])])
                geometry = {"type": "LineString", "coordinates": coords}
            
            # Polygon
            polygon = placemark.find('kml:Polygon', ns)
            if polygon is not None:
                outer = polygon.find('.//kml:outerBoundaryIs//kml:coordinates', ns)
                if outer is not None:
                    coords = []
                    for c in outer.text.strip().split():
                        parts = c.split(',')
                        coords.append([float(parts[0]), float(parts[1])])
                    geometry = {"type": "Polygon", "coordinates": [coords]}

            if geometry:
                feature = {
                    "type": "Feature",
                    "properties": {
                        "name": name_text,
                        "description": desc_text,
                        "marker_color": marker_color  # ★ここに色を追加
                    },
                    "geometry": geometry
                }
                features.append(feature)

        geojson_data = {
            "type": "FeatureCollection",
            "features": features
        }

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(geojson_data, f, ensure_ascii=False, indent=2)

        print(f"成功！ {len(features)} 件のデータを変換しました（色情報込み）。")

    except Exception as e:
        print(f"エラーが発生しました: {e}")

if __name__ == "__main__":
    convert_kml_to_geojson_with_style()
