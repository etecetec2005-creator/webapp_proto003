import streamlit as st
import google.generativeai as genai
from PIL import Image, ImageOps
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
st.set_page_config(page_title="e-Photo_Construction", layout="centered")
st.title("📸 e-Photo 工事黒板版")

# --- リセット機能 ---
if "uploader_key" not in st.session_state:
    st.session_state["uploader_key"] = 0

def reset_app():
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.session_state["uploader_key"] = st.session_state.get("uploader_key", 0) + 1
    st.rerun()

if st.button("🔄 画面をリセットして最初に戻る"):
    reset_app()

img_file = st.file_uploader(
    "撮影または画像を選択", 
    type=["jpg", "jpeg", "png"], 
    key=f"uploader_{st.session_state['uploader_key']}",
    accept_multiple_files=False
)

if img_file:
    try:
        file_size_mb = img_file.size / (1024 * 1024)
        raw_img = Image.open(img_file)
        img = ImageOps.exif_transpose(raw_img)
        
        original_width, original_height = img.size
        
        # 1MB以上の場合は1/2にリサイズ（黒板の文字が見えなくなるのを防ぐため1/3より少し大きく）
        if file_size_mb >= 1.0:
            new_width = original_width // 2
            new_height = original_height // 2
            img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
            resize_msg = f"⚠️ リサイズ完了 ({file_size_mb:.2f}MB → 1/2)"
        else:
            new_width, new_height = original_width, original_height
            resize_msg = f"✅ オリジナル維持 ({file_size_mb:.2f}MB)"
        
        st.image(img, caption=f"{resize_msg} : {new_width}x{new_height}", use_container_width=True)

        # AI解析
        ai_title = "名称未設定"
        with st.spinner("Gemini が解析中..."):
            try:
                model = genai.GenerativeModel('gemini-2.0-flash-exp') # または最新のflash
                prompt = """この写真の内容を分析し、20文字以内の日本語タイトルを1つだけ出力してください。
特に工事現場や設備管理の記録用として適切な、具体的かつ写実的な名称にしてください。
写真に看板などの文字があれば、それを引用してください。"""
                
                response = model.generate_content([prompt, img])
                if response and response.text:
                    ai_title = response.text.strip().replace("\n", "").replace("/", "-")
            except Exception as e:
                st.warning("⚠️ AI解析が制限されました。")

        # 画像のBase64変換
        buffered = io.BytesIO()
        img.save(buffered, format="JPEG", quality=85)
        img_str = base64.b64encode(buffered.getvalue()).decode()

        st.success(f"工事名 確定: {ai_title}")
        
        # --- 工事黒板合成用JavaScript ---
        auto_save_script = f"""
        <div id="status" style="font-size:12px; color:gray; padding:10px; background:#f9f9f9; border-radius:5px; border-left: 5px solid #2e7d32; margin-top: 10px;">
            📍 黒板を合成して自動保存します...
        </div>
        <script>
        (async function() {{
            const status = document.getElementById('status');
            const aiTitle = "{ai_title}";
            const imgBase64 = "data:image/jpeg;base64,{img_str}";
            const oW = {new_width};
            const oH = {new_height};

            const now = new Date();
            const dateStr = now.getFullYear() + "/" + ('0' + (now.getMonth() + 1)).slice(-2) + "/" + ('0' + now.getDate()).slice(-2);
            const fileDateStr = now.getFullYear().toString().slice(-2) + ('0' + (now.getMonth() + 1)).slice(-2) + ('0' + now.getDate()).slice(-2) + ('0' + now.getHours()).slice(-2);

            navigator.geolocation.getCurrentPosition(
                async (pos) => {{
                    const lat = pos.coords.latitude;
                    const lon = pos.coords.longitude;
                    let stationName = "駅名不明";

                    try {{
                        const stRes = await fetch(`https://express.heartrails.com/api/json?method=getStations&x=${{lon}}&y=${{lat}}`);
                        const stData = await stRes.json();
                        if (stData.response && stData.response.station) {{
                            stationName = stData.response.station[0].name + "駅付近";
                        }}
                    }} catch (e) {{}}
                    drawBoard(aiTitle, stationName, dateStr);
                }},
                (err) => {{ drawBoard(aiTitle, "位置情報なし", dateStr); }},
                {{ enableHighAccuracy: true, timeout: 5000 }}
            );

            function drawBoard(title, loc, date) {{
                const canvas = document.createElement('canvas');
                const ctx = canvas.getContext('2d');
                const img = new Image();
                
                img.onload = function() {{
                    canvas.width = oW;
                    canvas.height = oH;
                    ctx.drawImage(img, 0, 0, oW, oH);
                    
                    // --- 黒板のサイズ設計 ---
                    const bW = oW * 0.35; // 幅は画像の35%
                    const bH = bW * 0.7;   // 高さは幅の70%
                    const margin = 20;
                    const bX = margin;
                    const bY = oH - bH - margin;

                    // 1. 黒板の本体
                    ctx.fillStyle = "#004d40"; // 深い緑色
                    ctx.shadowColor = 'rgba(0,0,0,0.5)';
                    ctx.shadowBlur = 10;
                    ctx.fillRect(bX, bY, bW, bH);
                    ctx.shadowBlur = 0;

                    // 2. 枠線
                    ctx.strokeStyle = "#ffffff";
                    ctx.lineWidth = 2;
                    ctx.strokeRect(bX + 5, bY + 5, bW - 10, bH - 10);

                    // 3. 区切り線
                    ctx.beginPath();
                    ctx.moveTo(bX + 5, bY + (bH * 0.35)); // 1段目
                    ctx.lineTo(bX + bW - 5, bY + (bH * 0.35));
                    ctx.moveTo(bX + 5, bY + (bH * 0.7));  // 2段目
                    ctx.lineTo(bX + bW - 5, bY + (bH * 0.7));
                    ctx.moveTo(bX + (bW * 0.25), bY + 5);  // 縦線
                    ctx.lineTo(bX + (bW * 0.25), bY + bH - 5);
                    ctx.stroke();

                    // 4. 文字
                    ctx.fillStyle = "white";
                    const fontSize = Math.floor(bH / 8);
                    ctx.font = "bold " + fontSize + "px sans-serif";
                    ctx.textBaseline = "middle";

                    // ラベル（左側）
                    ctx.font = fontSize * 0.6 + "px sans-serif";
                    ctx.fillText("工事名", bX + 10, bY + (bH * 0.17));
                    ctx.fillText("場　所", bX + 10, bY + (bH * 0.52));
                    ctx.fillText("日　付", bX + 10, bY + (bH * 0.85));

                    // 内容（右側）
                    ctx.font = "bold " + (fontSize * 0.7) + "px sans-serif";
                    ctx.fillText(title.substring(0, 12), bX + (bW * 0.28), bY + (bH * 0.17));
                    ctx.fillText(loc.substring(0, 12), bX + (bW * 0.28), bY + (bH * 0.52));
                    ctx.fillText(date, bX + (bW * 0.28), bY + (bH * 0.85));
                    
                    // ダウンロード
                    const link = document.createElement('a');
                    link.download = fileDateStr + "_photo.jpg";
                    link.href = canvas.toDataURL('image/jpeg', 0.9);
                    link.click();
                    
                    status.style.color = "#1b5e20";
                    status.innerText = "✅ 工事黒板を合成して保存しました。";
                }};
                img.src = imgBase64;
            }}
        }})();
        </script>
        """
        st.components.v1.html(auto_save_script, height=130)

    except Exception as outer_e:
        st.error("エラーが発生しました。")
