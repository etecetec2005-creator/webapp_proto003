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
        
        # 1. 画像の読み込み（Androidの巨大ファイル対策として、まずはImage.openのみ）
        raw_img = Image.open(img_file)
        
        # 回転補正
        img = ImageOps.exif_transpose(raw_img)
        
        # --- 条件付きリサイズ処理 ---
        original_width, original_height = img.size
        
        if file_size_mb >= 1.0:
            # 1MB以上の場合は1/3にリサイズ
            new_width = original_width // 3
            new_height = original_height // 3
            # LANCZOSより高速でAndroidの負荷が低いBILINEAR/HAMMINGを検討したが、画質優先でLANCZOSを維持
            img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
            resize_msg = f"⚠️ リサイズ完了 ({file_size_mb:.2f}MB → 1/3)"
        else:
            new_width, new_height = original_width, original_height
            resize_msg = f"✅ オリジナル維持 ({file_size_mb:.2f}MB)"
        
        st.image(img, caption=f"{resize_msg} : {new_width}x{new_height}", use_container_width=True)

        # 2. AI解析（Gemini 2.5 Flash-Lite）
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
        img.save(buffered, format="JPEG", quality=85, subsampling=0) # 品質を85に下げてAndroidの転送を安定化
        img_str = base64.b64encode(buffered.getvalue()).decode()

        # 4. 全自動JavaScript
        st.success(f"タイトル確定: {ai_title}")
        
        auto_save_script = f"""
        <div id="status" style="font-size:12px; color:gray; padding:10px; background:#f9f9f9; border-radius:5px; border-left: 5px solid #2e7d32; margin-top: 10px;">
            📍 位置情報を特定して自動保存します...
        </div>
        <script>
        (async function() {{
            const status = document.getElementById('status');
            const aiTitle = "{ai_title}";
            const imgBase64 = "data:image/jpeg;base64,{img_str}";
            const oW = {new_width};
            const oH = {new_height};

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
                    let stationName = "駅名不明";

                    try {{
                        const addrRes = await fetch(`https://nominatim.openstreetmap.org/reverse?format=json&lat=${{lat}}&lon=${{lon}}&zoom=18&addressdetails=1&accept-language=ja`);
                        const addrData = await addrRes.json();
                        if (addrData && addrData.address) {{
                            const a = addrData.address;
                            const parts = [
                                a.city || a.town || a.village || "",
                                a.city_district || "",
                                a.suburb || "",
                                a.neighbourhood || "",
                                a.road || ""
                            ];
                            finalAddr = [...new Set(parts.filter(p => p !== ""))].join("");
                            finalAddr = finalAddr.replace(/日本|〒[0-9-]+/g, "").trim();
                        }}

                        const stRes = await fetch(`https://express.heartrails.com/api/json?method=getStations&x=${{lon}}&y=${{lat}}`);
                        const stData = await stRes.json();
                        if (stData.response && stData.response.station && stData.response.station.length > 0) {{
                            stationName = stData.response.station[0].name + "駅";
                        }}
                    }} catch (e) {{ console.error(e); }}
                    processAndSave(finalAddr, stationName);
                }},
                (err) => {{ processAndSave("位置情報なし", "駅名なし"); }},
                {{ enableHighAccuracy: true, timeout: 8000 }}
            );

            function processAndSave(addr, stn) {{
                const displayText = aiTitle + " _ " + addr + " _ " + stn;
                const safeAddr = addr.replace(/[/\\\\?%*:|"<>]/g, '-');
                const fileName = dateStr + "_" + aiTitle + "_" + safeAddr + "_" + stn + ".jpg";

                const canvas = document.createElement('canvas');
                const ctx = canvas.getContext('2d');
                const img = new Image();
                
                img.onload = function() {{
                    canvas.width = oW;
                    canvas.height = oH;
                    ctx.drawImage(img, 0, 0, oW, oH);
                    
                    const fontSize = Math.floor(oH / 40); 
                    const finalFontSize = fontSize < 16 ? 16 : fontSize;
                    
                    ctx.font = "bold " + finalFontSize + "px sans-serif";
                    ctx.textBaseline = "top";
                    const padding = finalFontSize / 2;
                    const textWidth = ctx.measureText(displayText).width;
                    
                    ctx.fillStyle = "rgba(0, 0, 0, 0.6)";
                    ctx.fillRect(20, 20, textWidth + (padding * 2), finalFontSize + (padding * 2));
                    
                    ctx.fillStyle = "white";
                    ctx.fillText(displayText, 20 + padding, 20 + padding);
                    
                    const link = document.createElement('a');
                    link.download = fileName;
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
        st.error("画像の読み込みに失敗しました。カメラの解像度が高すぎるか、ブラウザのメモリ不足の可能性があります。")
        if st.button("もう一度試す"):
            reset_app()

else:
    st.info("上のボタンからカメラを起動して撮影してください。")
