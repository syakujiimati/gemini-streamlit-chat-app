import streamlit as st
import google.generativeai as genai
import os

# --- Gemini APIを呼び出す関数 (改修) ---
def get_gemini_response(persona_prompt, prompt_text_with_history):
    try:
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            return "エラー: APIキーが環境変数に設定されていません。", []

        genai.configure(api_key=api_key)
        model_name = 'gemini-1.5-flash-latest' # または他の利用可能なモデル
        try:
            model = genai.GenerativeModel(model_name)
        except Exception as e:
            return f"モデル '{model_name}' の読み込み中にエラー: {e}", []

        # ペルソナ指示をプロンプトの冒頭に組み込む
        persona_instruction = ""
        if persona_prompt and persona_prompt.strip(): # ペルソナが入力されている場合
            persona_instruction = f"あなたは以下のペルソナとして振る舞ってください。以降の会話では、このペルソナを一貫して演じること。\n--- ペルソナここから ---\n{persona_prompt.strip()}\n--- ペルソナここまで ---\n\n"
        
        # プロンプトに候補生成の指示を追加
        full_prompt = f"""{persona_instruction}{prompt_text_with_history}

上記の会話と指定されたペルソナを踏まえ、通常の応答をしてください。
さらに、その応答の後に、ユーザーが次に送信しそうな自然な返答の候補を3つ提案してください。
候補は以下の形式で、区切り文字 '---suggestions---' の後に改行区切りで記述してください。
---suggestions---
[候補1]
[候補2]
[候補3]
候補の各行は[]で囲まず、テキストのみ記述してください。記号や番号も不要です。"""
        
        response = model.generate_content(full_prompt)
        
        raw_response_text = ""
        if response.candidates and response.candidates[0].content.parts:
            raw_response_text = response.candidates[0].content.parts[0].text
        else:
            error_message = "Geminiからの応答がありませんでした。"
            if hasattr(response, 'prompt_feedback') and response.prompt_feedback:
                error_message += f" プロンプトフィードバック: {response.prompt_feedback}"
            return error_message, []

        # 応答テキストを通常のメッセージと候補に分割
        if "---suggestions---" in raw_response_text:
            parts = raw_response_text.split("---suggestions---", 1)
            main_message = parts[0].strip()
            suggestions_text = parts[1].strip()
            suggestions_list = [s.strip() for s in suggestions_text.split('\n') if s.strip()]
            return main_message, suggestions_list[:3] 
        else:
            return raw_response_text.strip(), []

    except Exception as e:
        return f"API呼び出し中に予期せぬエラーが発生しました: {e}", []
# --- Gemini APIを呼び出す関数の終わり ---

st.title("Gemini カスタムペルソナチャットボット")

# --- サイドバーにペルソナ入力欄を設置 ---
st.sidebar.title("ペルソナ設定")
default_persona = "あなたは親切でフレンドリーなアシスタントです。丁寧な言葉遣いを心がけてください。"
# st.session_state を使ってペルソナを保持
if "persona" not in st.session_state:
    st.session_state.persona = default_persona

current_persona = st.sidebar.text_area(
    "AIのペルソナを入力してください:", 
    value=st.session_state.persona, 
    height=150,
    help="例：元気な女子高生、冷静沈着な執事、特定の専門知識を持つアドバイザーなど。口調や性格、役割を記述します。"
)
if current_persona != st.session_state.persona:
    st.session_state.persona = current_persona
    # ペルソナ変更時にチャット履歴をクリアするかどうかは選択可能
    # st.session_state.messages = [] # クリアする場合
    # st.session_state.suggestions = [] # クリアする場合
    st.sidebar.success("ペルソナが更新されました！")
    # st.rerun() # 必要であれば即時再実行

# ------------------------------------

# セッションステートの初期化 (チャット履歴と候補)
if "messages" not in st.session_state:
    st.session_state.messages = []
if "suggestions" not in st.session_state:
    st.session_state.suggestions = []
if "user_input" not in st.session_state:
    st.session_state.user_input = ""


# チャット履歴の表示
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"].replace('\n', '  \n'))

# 候補ボタンの表示と処理
if st.session_state.suggestions:
    # 列の数を動的に変更（最大3列）
    num_suggestions = len(st.session_state.suggestions)
    if num_suggestions > 0:
        cols = st.columns(num_suggestions)
        for i, suggestion_text in enumerate(st.session_state.suggestions):
            if cols[i].button(suggestion_text, key=f"suggestion_{i}"):
                st.session_state.user_input = suggestion_text
                st.session_state.suggestions = [] 
                st.rerun()

# チャット入力欄
manual_input = st.chat_input("メッセージを入力してください...", key="chat_input_manual")
if manual_input:
    st.session_state.user_input = manual_input
    st.session_state.suggestions = []
    # st.rerun() # 手動入力時も即座に処理したい場合はrerun

# ユーザー入力があった場合の処理
if st.session_state.user_input:
    current_user_input_text = st.session_state.user_input
    st.session_state.user_input = "" # 処理後にクリア

    st.session_state.messages.append({"role": "user", "content": current_user_input_text})
    # ユーザーメッセージの表示は次のrerun時にまとめて行われるようにする
    # (st.rerun()がこのブロックの最後に呼ばれるため)

    # Geminiに送る会話履歴を作成
    prompt_for_gemini_history = ""
    for msg in st.session_state.messages: # 直近の数件の履歴を使うなど、工夫も可能
        prompt_for_gemini_history += f"{msg['role']}: {msg['content']}\n"
    # 最後のAIの応答を促す部分を調整 (ユーザーの入力で終わるように)
    # prompt_for_gemini_history += "assistant: " 
    
    # 現在設定されているペルソナを取得
    active_persona = st.session_state.get("persona", default_persona) # personaがなければデフォルト

    with st.spinner("Geminiが考え中..."):
        assistant_response, new_suggestions = get_gemini_response(active_persona, prompt_for_gemini_history)
    
    st.session_state.messages.append({"role": "assistant", "content": assistant_response})
    st.session_state.suggestions = new_suggestions
    st.rerun() # メッセージと候補を更新して表示