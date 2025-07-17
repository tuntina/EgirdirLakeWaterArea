# app.py

import sys, io
# Python 3 ortamında Earth Engine kütüphanesinin StringIO import hatasını önlemek için the StringIO modülünü io'ya yönlendiriyoruz
sys.modules['StringIO'] = io

import os # İşletim sistemi ile ilgili yol ve dosya işlemleri için
from flask import Flask, render_template, request
import ee # Google Earth Engine Python API
import geopandas as gpd # Coğrafi veri (shapefile) işlemleri için   
import geemap.foliumap as geemap  # Folium tabanlı interactive harita görselleştirme

# ----------------------------------------------------
# 1) Flask ve Earth Engine Başlatma
# ----------------------------------------------------
app = Flask(__name__)

try:
    ee.Initialize(project='even-sun-457317-v8') # Mevcut GCP projesi ile EE initialize edilir
except Exception:
    ee.Authenticate()  # Eğer kimlik doğrulama yapılmamışsa kullanıcıdan izin istenir
    ee.Initialize(project='even-sun-457317-v8') # Kimlik doğrulama sonrasında yeniden initialize edilir


# ----------------------------------------------------
# 2) Boundary Shapefile Yükleme
# ----------------------------------------------------
base_dir = os.path.dirname(os.path.abspath(__file__)) # Mevcut dosyanın bulunduğu dizin
boundary_path = os.path.join(base_dir, 'boundary', 'egirdir_2024.shp') # Shapefile yolunu oluşturur
gdf = gpd.read_file(boundary_path).to_crs('EPSG:4326') # Shapefile'ı GeoPandas ile okur ve WGS84 (EPSG:4326) koordinat sistemine dönüştürür
fc = geemap.geopandas_to_ee(gdf) # GeoPandas DataFrame'i Google Earth Engine FeatureCollection'a dönüştürür


# ----------------------------------------------------
# 3) Otsu Eşik Fonksiyonu
# ----------------------------------------------------
    
   # Tek bantlı bir EE Image için Otsu algoritmasıyla optimal eşik değeri hesaplar.
   # 1) reduceRegion ile histogram verilerini alır
   # 2) bucketMeans ve histogram counts dizilerini kullanarak inter-class varyansı hesaplar
   # 3) En yüksek varyansa karşılık gelen eşik değerini döner
    
def otsu_threshold(image, feature):
        # Histogram verisini al (255 bucket, 30m çözünürlük, bestEffort)
    band = image.bandNames().get(0).getInfo()
    stats = image.reduceRegion(ee.Reducer.histogram(255), feature, 30, bestEffort=True).getInfo().get(band, {})
    counts = stats.get('histogram', [])# Histogram değerleri (piksel sayıları)
    means = stats.get('bucketMeans', [])# Her bucket ortalama değeri
    if not counts or not means:
        return 0# Veri yoksa sıfır döndür
    total = sum(counts) # Toplam piksel sayısı
    sum_mean = sum(c*m for c,m in zip(counts, means)) # Toplam ortalama ağırlıklı
    best_var = 0 # En iyi varyans
    thresh = means[0]  # Başlangıç eşiği
    w0 = 0 # Sınıf 0 ağırlığı
    sum0 = 0 # Sınıf 0 toplam
    for c, m in zip(counts, means):  # Her bucket için varyans hesabı
        w0 += c
        if w0 == 0 or w0 == total:
            continue
        sum0 += c*m
        m0 = sum0 / w0
        w1 = total - w0
        m1 = (sum_mean - sum0) / w1
        var_between = w0 * w1 * (m0 - m1)**2
        if var_between > best_var:
            best_var = var_between
            thresh = m
    return thresh

# ----------------------------------------------------
# 4) Su Maskesi Fonksiyonları
# ----------------------------------------------------

    #Sentinel-1 koleksiyonundan belirli polarizasyonda ve tarih aralığında
    #median kompozit oluşturur, Otsu eşikleme ile su maskesi çıkarır.

def fetch_s1_mask(polar, start, end, feature):
    coll = (ee.ImageCollection('COPERNICUS/S1_GRD')
            .filterBounds(feature) # Sadece shapefile sınırı içindeki görüntüler
            .filterDate(start, end)# Tarih filtresi
            .filter(ee.Filter.listContains('transmitterReceiverPolarisation', polar))
            .filter(ee.Filter.eq('orbitProperties_pass', 'ASCENDING'))
            .select(polar))  # Sadece seçilen polarizasyon bandı
    if coll.size().getInfo() == 0:
        return None # Görüntü yoksa None döndür
    img = coll.median() # Medyan kompozit oluşturur 
    thresh = otsu_threshold(img.select(polar), feature) # Eşik değeri
    return img.lt(thresh).selfMask().clip(feature) # Eşik altındaki pikselleri su kabul et

def fetch_s2_mask(method, start, end, feature):
    #Sentinel-2 koleksiyonundan bulut filtresi uygulayıp median kompozit oluşturur,
    #NDWI veya MNDWI hesaplar, Otsu eşikleme ile su maskesi çıkarır.
    coll = (ee.ImageCollection("COPERNICUS/S2_HARMONIZED")
            .filterBounds(feature)
            .filterDate(start, end)
            .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 10))) # %10 bulut altındaki görüntüler
    if coll.size().getInfo() == 0:
        return None
    img = coll.median()
        # NDWI veya MNDWI formülü
        # NDWI: (B3 - B8) / (B3 + B8)
        # MNDWI: (B3 - B11) / (B3 + B11)
    idx = img.normalizedDifference(['B3', 'B8']) if method == 'NDWI' else img.normalizedDifference(['B3', 'B11'])
    thresh = otsu_threshold(idx, feature)
    return idx.gt(thresh).selfMask().clip(feature)  # Eşik üzerindeki pikseller su


# ----------------------------------------------------
# 5) Ana Route
# ----------------------------------------------------
@app.route('/', methods=['GET', 'POST'])
def index():
    # Base map
    # Folium tabanlı harita nesnesi, Eğirdir merkezli
    m = geemap.Map(center=[38.05, 30.85], zoom=10)
    m.addLayer(fc.style(color='red', fillColor='00000000'), {}, 'Boundary')

    # Hazır değerler
    # Sonuçları saklamak için listeler
    area_vals = [None, None, None]# 1., 2. görüntü ve kesişim alanı (km²)
    label_texts = [None, None] # 1., 2. görüntü etiket metinleri
    masks = [None, None]# 1., 2. maskeleri
    colors = ['blue', 'yellow']

    if request.method == 'POST':
        for i in [1, 2]:
            sat = request.form.get(f'satellite{i}')
            method = request.form.get(f'method{i}')
            year = request.form.get(f'year{i}')
            month = request.form.get(f'month{i}')
            if not all([sat, method, year, month]):
                continue# Eksik seçim varsa atla
            # Harita katmanı etiketi: 'Sentinel-1 VV 2020-05' gibi
            label_texts[i-1] = f"{sat} {method} {year}-{int(month):02d}"
            # Başlangıç ve bitiş tarihleri string olarak
            start = f"{year}-{int(month):02d}-01"
            end_m = (int(month) % 12) + 1
            end_y = int(year) + (1 if int(month) == 12 else 0)
            end = f"{end_y}-{end_m:02d}-01"
            # Mask\          
            # İlgili maskeyi üret  
            mask = fetch_s1_mask(method, start, end, fc) if sat == 'Sentinel-1' else fetch_s2_mask(method, start, end, fc)
            masks[i-1] = mask
            if mask:
                # Alan hesaplama
                # Pixel alanı ölçümü => m², böl ve kilometreye çevir

                area_m2 = ee.Image.pixelArea().updateMask(mask).reduceRegion(
                    ee.Reducer.sum(), fc, 30
                ).get('area').getInfo() or 0
                area_vals[i-1] = round(area_m2 / 1e6, 2)
                # Haritaya ekle
                # Maskeyi haritaya katman olarak ekle

                m.addLayer(mask, {'palette': [colors[i-1]], 'opacity': 0.5}, label_texts[i-1])
        # Kesişim\        
        if masks[0] and masks[1]:
            inter = masks[0].And(masks[1])
            m.addLayer(inter, {'palette': ['purple'], 'opacity': 0.5}, 'Kesişim')
            inter_area = ee.Image.pixelArea().updateMask(inter).reduceRegion(
                ee.Reducer.sum(), fc, 30
            ).get('area').getInfo() or 0
            area_vals[2] = round(inter_area / 1e6, 2)
        # Lejant
        legend = {label_texts[0]: 'blue', label_texts[1]: 'yellow', 'Kesişim': 'purple'}
        m.add_legend(title='Lejant', legend_dict=legend, position='bottomright')

    # Map HTML
    # Harita HTML'ini oluştur ve şablona gönder

    map_html = m.to_html()
    # Uygulamayı port 5001'de ve tüm ara yüzlerden erişilebilir olarak çalıştır

    return render_template('index.html', map_html=map_html, area_vals=area_vals, label_texts=label_texts)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001)