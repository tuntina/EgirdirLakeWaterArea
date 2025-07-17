# EgirdirLakeWaterArea
# 📡 Su Yüzey Alanı İzleme Arayüzü – Eğirdir Gölü Örneği  
**Water Surface Monitoring Interface – Case Study of Lake Eğirdir**

Bu proje, Google Earth Engine ve Flask kullanılarak geliştirilmiş bir web uygulamasıdır. Kullanıcılar, Sentinel-1 (radar) ve Sentinel-2 (optik) uydu verileri ile Eğirdir Gölü’nün yıllık ortalama su yüzey alanını analiz edebilir ve görselleştirebilir.

This project is a web application built using Google Earth Engine and Flask. Users can analyze and visualize the annual average water surface area of Lake Eğirdir using Sentinel-1 (radar) and Sentinel-2 (optical) satellite data.

---

## 🔍 Özellikler / Features

- ✅ **Sentinel-1** verisiyle VV veya VH polarizasyon seçenekleri  
  ✅ **Sentinel-1** with VV or VH polarization options

- ✅ **Sentinel-2** için NDWI ve MNDWI su indeksleri  
  ✅ NDWI and MNDWI indices for **Sentinel-2**

- ✅ **Otsu histogram eşikleme** yöntemiyle otomatik su maskesi çıkarımı  
  ✅ Automatic water masking using **Otsu thresholding** based on image histograms

- ✅ Yıla göre analiz ve kullanıcıya görsel sonuçlar  
  ✅ Year-based analysis with interactive visual outputs

- ✅ Harita üzerinde karşılaştırmalı gösterim ve su alanı (km²) bilgisi  
  ✅ Side-by-side map comparison and water area display in square meters

---

## ⚙️ Kullanılan Teknolojiler / Technologies

- Python (Flask)
- Google Earth Engine Python API
- Geopandas & Geemap
- HTML / JavaScript

---

## 📁 Dosya Yapısı / File Structure

├── app.py # Flask backend + GEE integration
├── templates/
│ └── index.html # Web interface
├── static/ # (Optional) CSS or JS files
├── egirdir_2024.shp # Lake boundary shapefile
