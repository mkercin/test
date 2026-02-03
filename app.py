import streamlit as st
import pandas as pd
import requests
import io
import google.generativeai as genai
from PIL import Image

# Sayfa Ayarları
st.set_page_config(page_title="Sade Kütüphane", page_icon="📚", layout="centered")
st.title("📚 Ev Kütüphanesi")

# --- AYARLAR ---
KEENETIC_URL = st.secrets["KEENETIC_URL"]
WEBDAV_USER = st.secrets["WEBDAV_USER"]
WEBDAV_PASS = st.secrets["WEBDAV_PASS"]
GOOGLE_API_KEY = st.secrets["GOOGLE_API_KEY"]

# Model Ayarı (Gemini 2.0 Flash)
genai.configure(api_key=GOOGLE_API_KEY)
model = genai.GenerativeModel('gemini-2.5-flash')

# --- FONKSİYONLAR ---

def veriyi_getir():
    """Keenetic'ten CSV dosyasını okur, sütunları garantiye alır"""
    try:
        response = requests.get(KEENETIC_URL, auth=(WEBDAV_USER, WEBDAV_PASS))
        
        # Dosya yoksa veya boşsa
        if response.status_code == 404 or not response.text.strip():
            return pd.DataFrame(columns=["Kitap Adı", "Yazar"])

        response.raise_for_status()
        
        # Veriyi oku
        df = pd.read_csv(io.StringIO(response.content.decode('utf-8')), sep=';')
        
        # Sütun isimlerini zorla (Eğer dosya bozulursa kod çökmesin diye)
        # Sadece ilk 2 sütunu alıyoruz
        if len(df.columns) >= 2:
            df = df.iloc[:, :2] # İlk 2 sütunu seç
            df.columns = ["Kitap Adı", "Yazar"]
        else:
            df = pd.DataFrame(columns=["Kitap Adı", "Yazar"])
            
        return df

    except Exception as e:
        st.error(f"Veri Okuma Hatası: {e}")
        return pd.DataFrame(columns=["Kitap Adı", "Yazar"])

def veriyi_kaydet(df):
    """Listeyi Keenetic'e yazar"""
    try:
        csv_buffer = io.StringIO()
        df.to_csv(csv_buffer, index=False, sep=';')
        csv_data = csv_buffer.getvalue().encode('utf-8')
        
        response = requests.put(KEENETIC_URL, data=csv_data, auth=(WEBDAV_USER, WEBDAV_PASS))
        
        if response.status_code in [200, 201, 204]:
            return True
        else:
            st.error(f"Kayıt Başarısız. Kod: {response.status_code}")
            return False
    except Exception as e:
        st.error(f"Yazma Hatası: {e}")
        return False

def fotograftan_kitaplari_bul(image):
    """AI Sadece Kitap ve Yazar Okur"""
    
    # Görsel Optimizasyonu
    if image.mode != 'RGB':
        image = image.convert('RGB')
    image.thumbnail((1024, 1024))

    prompt = """
    Bu fotoğraftaki kitapların sırtlarını oku.
    Bana SADECE aşağıdaki CSV formatında bir liste ver. Başka hiçbir açıklama yazma.
    Markdown formatı kullanma (```csv yazma).
    
    Format:
    Kitap Adı;Yazar
    
    Örnek:
    Dune;Frank Herbert
    Nutuk;Atatürk
    """
    
    try:
        with st.spinner('Yapay zeka kitapları okuyor...'):
            response = model.generate_content([prompt, image])
            text = response.text.replace("```csv", "").replace("```", "").strip()
            return text
            
    except Exception as e:
        st.error(f"AI Hatası: {e}")
        return ""

# --- ARAYÜZ ---

# Sekmeler
tab1, tab2 = st.tabs(["🔍 Kitap Ara", "➕ Kitap Ekle"])

with tab1:
    df = veriyi_getir()
    st.write(f"Toplam Kitap: **{len(df)}**")
    
    arama = st.text_input("Kitap Ara", placeholder="Ad veya yazar gir...")
    if arama:
        # Basit filtreleme (AI'ya gerek yok, hız kazandırır)
        sonuc = df[df.apply(lambda row: row.astype(str).str.contains(arama, case=False).any(), axis=1)]
        st.dataframe(sonuc, use_container_width=True)
    else:
        st.dataframe(df, use_container_width=True)

with tab2:
    mode = st.radio("Ekleme Yöntemi", ["Fotoğrafla Tara", "Elle Ekle"])
    
    if mode == "Fotoğrafla Tara":
        uploaded_file = st.file_uploader("Raf Fotoğrafı", type=["jpg", "png", "jpeg"])
        
        if uploaded_file and st.button("Tara ve Kaydet"):
            image = Image.open(uploaded_file)
            st.image(image, caption='Yüklenen Fotoğraf', width=300)
            
            ai_text = fotograftan_kitaplari_bul(image)
            
            if ai_text:
                try:
                    # Gelen metni veriye çevir
                    df_ai = pd.read_csv(io.StringIO(ai_csv_text), sep=';', names=["Kitap Adı", "Yazar"])
                    
                    st.write("Algılananlar:")
                    st.dataframe(df_ai)
                    
                    # Kayıt İşlemi
                    df_mevcut = veriyi_getir()
                    df_son = pd.concat([df_mevcut, df_ai], ignore_index=True)
                    
                    if veriyi_kaydet(df_son):
                        st.success("✅ Kitaplar Veritabanına Eklendi!")
                        st.balloons()
                    
                except Exception as e:
                    st.error(f"Format hatası. AI çıktısı:\n{ai_text}")

    else: # Elle Ekle
        col1, col2 = st.columns(2)
        with col1: ad = st.text_input("Kitap Adı")
        with col2: yazar = st.text_input("Yazar")
        
        if st.button("Listeye Ekle"):
            if ad and yazar:
                df_mevcut = veriyi_getir()
                yeni = pd.DataFrame({"Kitap Adı": [ad], "Yazar": [yazar]})
                df_son = pd.concat([df_mevcut, yeni], ignore_index=True)
                
                if veriyi_kaydet(df_son):
                    st.success(f"{ad} eklendi!")
