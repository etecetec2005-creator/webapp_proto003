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
st.set_page_config(page_title="e-Photo_000", layout="centered")
st.title("📸 e-Photo📝黒板")

# --- URLパラメータによる工事件名の保持・復元 ---
url_params = st.query_params
initial_project_name = url_params.get("project_name", "")

if "project_name" not in st.session_state:
    st.session_state["project_name"] = initial_project_name

# 入力フォーム
input_val = st.text_input(
    "工事件名を入力してください（URLに保存されます）",
    value=st.session_state["project_name"],
    placeholder="例：〇〇ビル電気設備工事"
)

# 入力内容が変更されたらURLとセッションを更新
if input_val != st.session_state["project_name"]:
    st.session_state["project_name"] = input_val
    st.query_params["project_name"] = input_val
    st.rerun()

# --- 黒板の配置設定 ---
board_position = st.radio(
    "黒板の配置位置を選択してください",
    ["左下", "右下", "左上", "右上"],
    index=0,
    horizontal=True
)

# --- リセット機能 ---
if "uploader_key" not in st.session_state:
    st.session_state["uploader_key"] = 0

def reset_app():
    for key in list(st.session_state.keys()):
        if key not in ["project_name"]:
            del st.session_state[key]
    st.session_state["uploader_key"] = st.session_state.get("uploader_key", 0) + 1
    st.rerun()

if st.button("🔄 画面をリセットして最初に戻る"):
    reset_app()

# 工事件名ガード
if not st.session_state["project_name"]:
    st.warning("⚠️ 撮影の前に、ページ上部で「工事件名」を入力してください。")
    st.stop()

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
        
        if file_size_mb >= 1.0:
            new_width = original_width // 2
            new_height = original_height // 2
            img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
            resize_msg = f"⚠️ リサイズ完了 ({file_size_mb:.2f}MB → 1/2)"
        else:
            new_width, new_height = original_width, original_height
            resize_msg = f"✅ オリジナル維持 ({file_size_mb:.2f}MB)"
        
        st.image(img, caption=f"{resize_msg} : {new_width}x{new_height}", use_container_width=True)

        # 2. AI解析
        ai_title = "" 
        with st.spinner("Gemini 2.5 Flash-Lite が解析中..."):
            try:
                model = genai.GenerativeModel('gemini-2.5-flash-lite')
                prompt = """この写真の内容を分析し、20文字以内の日本語タイトルを1つだけ出力してください。
【留意事項】写真には電気設備が写っている場合が多くあります。その場合、特に写実的で具体的なタイトルとしてください。
写真に文字や数字が写っている場合はタイトルにその内容も加えてください。
ただし、その文字や数字だけのタイトルにはしないでください。"""
                
                response = model.generate_content([prompt, img])
                if response and response.text:
                    ai_title = response.text.strip().replace("\n", "").replace("/", "-").replace(" ", "")
            except Exception as e:
                st.warning("⚠️ AI解析がタイムアウトしました。備考欄は空欄となります。")

        # 3. 画像のBase64変換
        buffered = io.BytesIO()
        img.save(buffered, format="JPEG", quality=85, subsampling=0) 
        img_str = base64.b64encode(buffered.getvalue()).decode()

        # 4. 全自動JavaScript
        if ai_title:
            st.success(f"解析タイトル確定: {ai_title}")
        
        auto_save_script = f"""
        <div id="status" style="font-size:12px; color:gray; padding:10px; background:#f9f9f9; border-radius:5px; border-left: 5px solid #2e7d32; margin-top: 10px;">
            📍 工事黒板を合成して自動保存します...
        </div>
        <script>
        (async function() {{
            const status = document.getElementById('status');
            const projectName = "{st.session_state['project_name']}";
            const aiTitle = "{ai_title}";
            const imgBase64 = "data:image/jpeg;base64,{img_str}";
            const oW = {new_width};
            const oH = {new_height};
            const posSetting = "{board_position}";

            const now = new Date();
            const dateStr = now.getFullYear() + "/" + ('0' + (now.getMonth() + 1)).slice(-2) + "/" + ('0' + now.getDate()).slice(-2);
            const fileDateStr = now.getFullYear().toString().slice(-2) + 
                             ('0' + (now.getMonth() + 1)).slice(-2) + 
                             ('0' + now.getDate()).slice(-2) + 
                             ('0' + now.getHours()).slice(-2) + 
                             ('0' + now.getMinutes()).slice(-2);

            navigator.geolocation.getCurrentPosition(
                async (pos) => {{
                    const lat = pos.coords.latitude;
                    const lon = pos.coords.longitude;
                    let stationName = "駅名不明";

                    try {{
                        const stRes = await fetch(`https://express.heartrails.com/api/json?method=getStations&x=${{lon}}&y=${{lat}}`);
                        const stData = await stRes.json();
                        if (stData.response && stData.response.station && stData.response.station.length > 0) {{
                            stationName = stData.response.station[0].name + "駅";
                        }}
                    }} catch (e) {{ console.error(e); }}
                    drawBoard(projectName, stationName, dateStr, aiTitle, posSetting);
                }},
                (err) => {{ drawBoard(projectName, "位置情報なし", dateStr, aiTitle, posSetting); }},
                {{ enableHighAccuracy: true, timeout: 8000 }}
            );

            function drawBoard(pjName, loc, date, note, pos) {{
                const canvas = document.createElement('canvas');
                const ctx = canvas.getContext('2d');
                const img = new Image();
                
                img.onload = function() {{
                    canvas.width = oW;
                    canvas.height = oH;
                    ctx.drawImage(img, 0, 0, oW, oH);
                    
                    const bW = oW * 0.3; 
                    const bH = bW * 0.75; 
                    const margin = 10;
                    
                    let bX, bY;
                    if (pos === "左下") {{ bX = margin; bY = oH - bH - margin; }}
                    else if (pos === "右下") {{ bX = oW - bW - margin; bY = oH - bH - margin; }}
                    else if (pos === "左上") {{ bX = margin; bY = margin; }}
                    else if (pos === "右上") {{ bX = oW - bW - margin; bY = margin; }}

                    ctx.fillStyle = "#004d40"; 
                    ctx.fillRect(bX, bY, bW, bH);
                    ctx.strokeStyle = "#ffffff";
                    ctx.lineWidth = 2;
                    ctx.strokeRect(bX + 3, bY + 3, bW - 6, bH - 6);

                    ctx.beginPath();
                    ctx.moveTo(bX + 3, bY + (bH * 0.25)); 
                    ctx.lineTo(bX + bW - 3, bY + (bH * 0.25));
                    ctx.moveTo(bX + 3, bY + (bH * 0.5)); 
                    ctx.lineTo(bX + bW - 3, bY + (bH * 0.5));
                    ctx.moveTo(bX + 3, bY + (bH * 0.75)); 
                    ctx.lineTo(bX + bW - 3, bY + (bH * 0.75));
                    ctx.moveTo(bX + (bW * 0.35), bY + 3); 
                    ctx.lineTo(bX + (bW * 0.35), bY + bH - 3);
                    ctx.stroke();

                    ctx.fillStyle = "white";
                    const fontSize = Math.floor(bH / 11);
                    
                    // 改行描画用関数
                    function drawTextWithWrap(text, x, y) {{
                        if (text.length > 10) {{
                            const line1 = text.substring(0, 10);
                            const line2 = text.substring(10, 20);
                            ctx.font = "bold " + (fontSize * 0.85) + "px sans-serif";
                            ctx.fillText(line1, x, y - (fontSize * 0.4));
                            ctx.fillText(line2, x, y + (fontSize * 0.5));
                        }} else {{
                            ctx.font = "bold " + fontSize + "px sans-serif";
                            ctx.fillText(text, x, y);
                        }}
                    }}

                    ctx.textBaseline = "middle";
                    ctx.font = fontSize * 0.8 + "px sans-serif";
                    ctx.fillText("工事件名", bX + 8, bY + (bH * 0.125));
                    ctx.fillText("工事場所", bX + 8, bY + (bH * 0.375));
                    ctx.fillText("日　　付", bX + 8, bY + (bH * 0.625));
                    ctx.fillText("備　　考", bX + 8, bY + (bH * 0.875));

                    // 内容の描画（改行対応）
                    drawTextWithWrap(pjName, bX + (bW * 0.38), bY + (bH * 0.125));
                    drawTextWithWrap(loc, bX + (bW * 0.38), bY + (bH * 0.375));
                    drawTextWithWrap(date, bX + (bW * 0.38), bY + (bH * 0.625));
                    drawTextWithWrap(note, bX + (bW * 0.38), bY + (bH * 0.875));
                    
                    const link = document.createElement('a');
                    const downloadName = note ? fileDateStr + "_" + note + ".jpg" : fileDateStr + "_photo.jpg";
                    link.download = downloadName;
                    link.href = canvas.toDataURL('image/jpeg', 0.85); 
                    link.click();
                    
                    status.style.color = "#1b5e20";
                    status.innerText = "✅ 保存完了。リセットを押して次の撮影へ";
                }};
                img.src = imgBase64;
            }}
        }})();
        </script>
        """
        st.components.v1.html(auto_save_script, height=130)

    except Exception as outer_e:
        st.error("画像の読み込みに失敗しました。")
        if st.button("もう一度試す"):
            reset_app()
else:
    st.info("上のボタンからカメラを起動して撮影してください。")
