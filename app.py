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
st.title("📸 e-Photo")

# --- セッション状態の初期化 ---
if "project_name" not in st.session_state:
    st.session_state["project_name"] = ""

if "uploader_key" not in st.session_state:
    st.session_state["uploader_key"] = 0

# --- 工事件名の入力エリア ---
st.session_state["project_name"] = st.text_input(
    "工事件名を入力してください（アプリを閉じるまで保持されます）",
    value=st.session_state["project_name"],
    placeholder="例：〇〇ビル電気設備工事"
)

# --- リセット機能 ---
def reset_app():
    # project_name 以外を削除
    for key in list(st.session_state.keys()):
        if key != "project_name":
            del st.session_state[key]
    st.session_state["uploader_key"] = st.session_state.get("uploader_key", 0) + 1
    st.rerun()

if st.button("🔄 画面をリセットして最初に戻る"):
    reset_app()

# 工事件名が入力されていない場合はアップローダーを表示しない
if not st.session_state["project_name"]:
    st.warning("⚠️ 撮影の前に、ページ上部で「工事件名」を入力してください。")
    st.stop()

# Androidの挙動を安定させるため、単一ファイル選択を明示
img_file = st.file_uploader(
    "撮影または画像を選択", 
    type=["jpg", "jpeg", "png"], 
    key=f"uploader_{st.session_state['uploader_key']}",
    accept_multiple_files=False
)

if img_file:
    try:
        # ファイルサイズの取得 (MB)
        file_size_mb = img_file.size / (1024 * 1024)
        
        # 1. 画像の読み込み
        raw_img = Image.open(img_file)
        
        # 回転補正
        img = ImageOps.exif_transpose(raw_img)
        
        # --- 条件付きリサイズ処理 ---
        original_width, original_height = img.size
        
        if file_size_mb >= 1.0:
            # 1MB以上の場合は1/2にリサイズ（黒板の文字視認性のため1/2を推奨）
            new_width = original_width // 2
            new_height = original_height // 2
            img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
            resize_msg = f"⚠️ リサイズ完了 ({file_size_mb:.2f}MB → 1/2)"
        else:
            new_width, new_height = original_width, original_height
            resize_msg = f"✅ オリジナル維持 ({file_size_mb:.2f}MB)"
        
        st.image(img, caption=f"{resize_msg} : {new_width}x{new_height}", use_container_width=True)

        # 2. AI解析（Gemini 2.5 Flash-Lite）
        # ※黒板には入力した工事件名を使い、ファイル名や補助としてAIタイトルを利用
        ai_title = "名称未設定"
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
                st.warning("⚠️ AI解析がタイムアウトしました。タイトルなしで続行します。")

        # 3. 画像のBase64変換
        buffered = io.BytesIO()
        img.save(buffered, format="JPEG", quality=85, subsampling=0) 
        img_str = base64.b64encode(buffered.getvalue()).decode()

        # 4. 全自動JavaScript（黒板描画機能付き）
        st.success(f"解析タイトル: {ai_title}")
        
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
                    drawBoard(projectName, stationName, dateStr);
                }},
                (err) => {{ drawBoard(projectName, "位置情報なし", dateStr); }},
                {{ enableHighAccuracy: true, timeout: 8000 }}
            );

            function drawBoard(pjName, loc, date) {{
                const canvas = document.createElement('canvas');
                const ctx = canvas.getContext('2d');
                const img = new Image();
                
                img.onload = function() {{
                    canvas.width = oW;
                    canvas.height = oH;
                    ctx.drawImage(img, 0, 0, oW, oH);
                    
                    // --- 黒板のサイズ・位置設定 ---
                    const bW = oW * 0.4; 
                    const bH = bW * 0.65;
                    const margin = 20;
                    const bX = margin;
                    const bY = oH - bH - margin;

                    // 1. 黒板の本体
                    ctx.fillStyle = "#004d40"; 
                    ctx.fillRect(bX, bY, bW, bH);

                    // 2. 枠線
                    ctx.strokeStyle = "#ffffff";
                    ctx.lineWidth = 3;
                    ctx.strokeRect(bX + 5, bY + 5, bW - 10, bH - 10);

                    // 3. 区切り線
                    ctx.beginPath();
                    ctx.moveTo(bX + 5, bY + (bH * 0.35)); 
                    ctx.lineTo(bX + bW - 5, bY + (bH * 0.35));
                    ctx.moveTo(bX + 5, bY + (bH * 0.7)); 
                    ctx.lineTo(bX + bW - 5, bY + (bH * 0.7));
                    ctx.moveTo(bX + (bW * 0.3), bY + 5); 
                    ctx.lineTo(bX + (bW * 0.3), bY + bH - 5);
                    ctx.stroke();

                    // 4. 文字描画
                    ctx.fillStyle = "white";
                    const fontSize = Math.floor(bH / 9);
                    ctx.textBaseline = "middle";

                    // ラベル
                    ctx.font = fontSize * 0.7 + "px sans-serif";
                    ctx.fillText("工事件名", bX + 12, bY + (bH * 0.17));
                    ctx.fillText("工事場所", bX + 12, bY + (bH * 0.52));
                    ctx.fillText("日　付", bX + 12, bY + (bH * 0.85));

                    // 内容（入力された工事件名を使用）
                    ctx.font = "bold " + fontSize + "px sans-serif";
                    ctx.fillText(pjName.substring(0, 15), bX + (bW * 0.33), bY + (bH * 0.17));
                    ctx.fillText(loc.substring(0, 15), bX + (bW * 0.33), bY + (bH * 0.52));
                    ctx.fillText(date, bX + (bW * 0.33), bY + (bH * 0.85));
                    
                    // 保存
                    const link = document.createElement('a');
                    link.download = fileDateStr + "_" + aiTitle + ".jpg";
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
