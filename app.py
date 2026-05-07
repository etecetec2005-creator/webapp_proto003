import streamlit as st
import google.generativeai as genai
from PIL import Image
import io
import os
import base64

# --- セキュリティ設定 ---
api_key = st.secrets.get("GEMINI_API_KEY") or os.environ.get("GEMINI_API_KEY")
if not api_key:
    st.error("APIキーが設定されていません。StreamlitのSecretsに登録してください。")
    st.stop()

genai.configure(api_key=api_key)

# --- 基本設定 ---
st.set_page_config(page_title="施錠よし！", layout="centered")

# 赤い点滅警告用のCSS
st.markdown("""
    <style>
    @keyframes blink {
        0% { opacity: 1; }
        50% { opacity: 0.3; }
        100% { opacity: 1; }
    }
    .warning-box {
        background-color: #FF0000;
        color: white;
        padding: 20px;
        border-radius: 10px;
        text-align: center;
        font-weight: bold;
        font-size: 24px;
        animation: blink 1s infinite;
        margin: 20px 0;
    }
    </style>
    """, unsafe_allow_html=True)

st.title("🔐 施錠よし！")
st.caption("門扉・閂・南京錠の施錠状態をAIで確認します")

# 入力ソースの選択
input_method = st.radio("入力方法を選択してください", ["カメラで撮影", "画像をアップロード"])

img_file = None
if input_method == "カメラで撮影":
    img_file = st.camera_input("門扉を撮影", key="lock_camera")
else:
    img_file = st.file_uploader("画像を選択してください", type=["jpg", "jpeg", "png"], key="lock_upload")

if img_file:
    # 1. 画像の読み込み
    img = Image.open(img_file)
    width, height = img.size 
    st.image(img, caption="解析中...")

    # 2. AI解析
    ai_analysis = ""
    is_locked = True # 判定フラグ
    
    with st.spinner("施錠状態を詳細に分析中..."):
        try:
            # 最新のFlashモデルを使用
            model = genai.GenerativeModel('gemini-2.0-flash')
            
            prompt = """
提出された写真の門扉、閂（かんぬき）、南京錠の施錠状態を厳密に分析してください。

【分析手順】
1. 門扉が閉じているか、閂が所定の位置にあるか、南京錠が掛かっているかを確認してください。
2. 施錠が不完全、または開いている場合は「未施錠」と判断してください。
3. 結果を100字以内で簡潔に説明してください。
4. 出力の最後の一行に、判定結果に基づいて以下のいずれかを必ず記述してください。
   - 判定：施錠済み
   - 判定：未施錠
"""
            response = model.generate_content([prompt, img])
            
            if response and response.text:
                full_text = response.text
                ai_analysis = full_text.replace("判定：施錠済み", "").replace("判定：未施錠", "").strip()
                
                # 判定フラグのチェック
                if "判定：未施錠" in full_text:
                    is_locked = False
                
                st.subheader("📋 判定結果")
                
                # 警告表示（未施錠の場合）
                if not is_locked:
                    st.markdown('<div class="warning-box">⚠️ 警告：門扉が施錠されていません！</div>', unsafe_allow_html=True)
                    st.error(ai_analysis)
                else:
                    st.success("✅ 施錠が確認されました。")
                    st.info(ai_analysis)

        except Exception as e:
            st.error(f"⚠️ AI解析エラー: {e}")

    # 3. 画像のBase64変換（保存用）
    buffered = io.BytesIO()
    img.save(buffered, format="JPEG", quality=95)
    img_str = base64.b64encode(buffered.getvalue()).decode()

    # 4. 自動保存JS（位置情報＋結果埋め込み）
    status_label = "施錠確認" if is_locked else "未施錠警告"
    
    auto_save_script = f"""
    <div id="status" style="font-size:12px; color:gray; padding:10px; background:#f9f9f9; border-radius:5px;">
        📍 位置情報を取得して記録を保存します...
    </div>
    <script>
    (async function() {{
        const status = document.getElementById('status');
        const label = "{status_label}";
        const imgBase64 = "data:image/jpeg;base64,{img_str}";
        const oW = {width};
        const oH = {height};

        const now = new Date();
        const dateStr = now.getFullYear().toString().slice(-2) + 
                        ('0' + (now.getMonth() + 1)).slice(-2) + 
                        ('0' + now.getDate()).slice(-2) + 
                        ('0' + now.getHours()).slice(-2) + 
                        ('0' + now.getMinutes()).slice(-2);

        navigator.geolocation.getCurrentPosition(
            async (pos) => {{
                const lat = pos.coords.latitude;
                const lon = pos.coords.longitude;
                let finalAddr = "住所不明";

                try {{
                    const addrRes = await fetch(`https://nominatim.openstreetmap.org/reverse?format=json&lat=${{lat}}&lon=${{lon}}&zoom=18&addressdetails=1&accept-language=ja`);
                    const addrData = await addrRes.json();
                    if (addrData && addrData.address) {{
                        const a = addrData.address;
                        finalAddr = (a.city || a.town || "") + (a.suburb || "") + (a.road || "");
                    }}
                }} catch (e) {{ console.error(e); }}
                
                saveImage(finalAddr);
            }},
            (err) => {{ saveImage("位置情報なし"); }},
            {{ enableHighAccuracy: true, timeout: 7000 }}
        );

        function saveImage(addr) {{
            const displayText = label + " | " + addr + " | " + dateStr;
            const fileName = dateStr + "_" + label + ".jpg";

            const canvas = document.createElement('canvas');
            const ctx = canvas.getContext('2d');
            const img = new Image();
            
            img.onload = function() {{
                canvas.width = oW;
                canvas.height = oH;
                ctx.drawImage(img, 0, 0, oW, oH);
                
                const fontSize = Math.floor(oH / 30); 
                ctx.font = "bold " + fontSize + "px sans-serif";
                
                // テキスト背景
                ctx.fillStyle = "{'rgba(0, 150, 0, 0.7)' if is_locked else 'rgba(255, 0, 0, 0.8)'}";
                const txtWidth = ctx.measureText(displayText).width;
                ctx.fillRect(20, 20, txtWidth + 20, fontSize + 20);
                
                ctx.fillStyle = "white";
                ctx.fillText(displayText, 30, 20 + fontSize);
                
                const link = document.createElement('a');
                link.download = fileName;
                link.href = canvas.toDataURL('image/jpeg', 0.9);
                link.click();
                
                status.style.color = "green";
                status.innerText = "✅ 保存完了: " + fileName;
            }};
            img.src = imgBase64;
        }}
    }})();
    </script>
    """
    st.components.v1.html(auto_save_script, height=100)
