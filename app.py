import streamlit as st
import pandas as pd
import requests
import io
import google.generativeai as genai

# Sayfa Ayarları
st.set_page_config(page_title="Ev Kütüphanem", page_icon="📚")

st.title("📚 Evdeki Kütüphanem")
st.write("Keenetic Modem Sunucusuna Bağlanılıyor...")

# --- AYARLARI GÜVENLİ BİR ŞEKİLDE AL ---
# Bu bilgileri Streamlit Secrets kısmından çekeceğiz (Aşağıda anlatacağım)
KEENETIC_URL = st.secrets["KEENETIC_URL"]
WEBDAV_USER = st.secrets["WEBDAV_USER"]
WEBDAV_PASS = st.secrets["WEBDAV_PASS"]
GOOGLE_API_KEY = st.secrets["GOOGLE_API_KEY"]

# --- FONKSİYONLAR ---

# 1. Keenetic'ten Veriyi Çek (Cache kullanarak her seferinde modemi yormayalım)
@st.cache_data(ttl=300) # 5 dakikada bir veriyi yeniler
def veriyi_getir():
    try:
        response = requests.get(KEENETIC_URL, auth=(WEBDAV_USER, WEBDAV_PASS))
        response.raise_for_status() # Hata varsa durdur
        # CSV'yi Pandas DataFrame'e çevir
        df = pd.read_csv(io.StringIO(response.content.decode('utf-8')))
        return df
    except Exception as e:
        st.error(f"Veri çekilemedi: {e}")
        return None

# 2. Gemini Yapay Zeka Sorgusu
def yapay_zekaya_sor(df, soru):
    genai.configure(api_key=GOOGLE_API_KEY)
    model = genai.GenerativeModel('gemini-pro')
    
    # Veriyi metne çevirip prompte ekliyoruz
    liste_metni = df.to_string(index=False)
    
    prompt = f"""
    Aşağıda kütüphanemdeki kitapların listesi var.
    Kullanıcı sana bir kitap soracak. Listeye bak ve şu kurallara göre cevap ver:
    1. Kitap listede kesinlikle varsa "VAR" de ve hangi rafta/konumda olduğunu söyle.
    2. Kitap yoksa ama yazarın başka kitabı varsa onu öner.
    3. Hiçbiri yoksa nazikçe "Maalesef evde yok" de.
    4. Kullanıcı kitap sormuyorsa (örn: "kaç kitap var"), listeye göre analiz yap.
    
    LİSTE:
    {liste_metni}
    
    KULLANICI SORUSU: {soru}
    """
    
    with st.spinner('Yapay zeka kitaplığı tarıyor...'):
        response = model.generate_content(prompt)
        return response.text

# --- ARAYÜZ AKIŞI ---

df = veriyi_getir()

if df is not None:
    # 1. Tüm listeyi göster (İsteğe bağlı, tablo olarak bakarız)
    with st.expander("📖 Tüm Kitap Listesini Gör"):
        st.dataframe(df)

    # 2. Arama Kutusu
    soru = st.text_input("Hangi kitabı arıyorsun?", placeholder="Örn: Dune evde var mı?")

    if soru:
        cevap = yapay_zekaya_sor(df, soru)
        st.success("Sonuç:")
        st.write(cevap)
        
        # Manuel filtreleme kontrolü (AI hata yaparsa diye)
        st.markdown("---")
        st.caption("Veritabanı Ham Sonuçları (Arama kelimesini içerenler):")
        basit_arama = df[df.apply(lambda row: row.astype(str).str.contains(soru, case=False).any(), axis=1)]
        st.table(basit_arama)

else:
    st.warning("Keenetic sunucusuna ulaşılamadı. Modemin açık olduğundan emin ol.")