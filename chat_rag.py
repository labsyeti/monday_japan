import streamlit as st
from datetime import datetime, timedelta, timezone
from supabase_vector_client import ActivityWatchSupabaseClient

# Nepal timezone (UTC+5:45)
NEPAL_TZ = timezone(timedelta(hours=5, minutes=45))

# --- Translations ---
TRANSLATIONS = {
    'en': {
        'title': '🤖 ActivityWatch RAG Chat',
        'loading': 'Loading...',
        'language_selector': 'Select Language',
        'search_mode_label': 'Search Mode',
        'search_input_placeholder': 'Ask me anything about your computer usage...',
        'search_button': 'Search',
        'show_more_button': 'Show More',
        'clear_chat_button': 'Clear Chat',
        'vector_search': 'Vector (semantic)',
        'text_search': 'Text (exact)',
        'database_stats': '📊 Database Statistics',
        'total_events': 'Total Events',
        'total_buckets': 'Total Buckets',
        'last_updated': 'Last Updated',
        'example_queries': '💡 Example Queries',
        'example_queries_list': [
            'How much time did I spend coding?',
            'How much time did I spend on WhatsApp?',
            'What apps do I use most?'
        ],
        'search_tips': '💡 Search Tips',
        'search_tips_list': [
            'Use specific app names: "Cursor", "WhatsApp", "Chrome"',
            'Ask about time periods: "today", "yesterday", "this week"',
            'Search by activity type: "coding", "browsing", "social media"',
            'Combine terms: "Cursor yesterday", "WhatsApp this week"'
        ],
        'search_info': '🔍 **Search Info:**',
        'search_mode': 'Search Mode',
        'query': 'Query',
        'results_found': 'Results Found',
        'search_time': 'Search Time',
        'top_apps': 'Top Apps',
        'app': 'App',
        'duration': 'Duration',
        'time': 'Time',
        'title_col': 'Title',
        'page': 'Page',
        'of': 'of',
        'showing_events': 'Showing events',
        'more_events': 'more events',
        'last_page': 'Last page',
        'previous': '⬅️ Previous',
        'next': 'Next ➡️',
        'clear_chat_confirm': 'Are you sure you want to clear the chat history?',
        'yes': 'Yes',
        'no': 'No',
        'no_results': 'No matching events found.',
        'similarity_threshold': 'Similarity Threshold',
        'max_results': 'Max Results',
        'time_filter': 'Time Filter',
        'bucket_filter': 'Bucket Filter'
    },
    'ja': {
        'title': '🤖 ActivityWatch RAGチャット',
        'loading': '読み込み中...',
        'language_selector': '言語を選択',
        'search_mode_label': '検索モード',
        'search_input_placeholder': 'コンピュータの使用状況について質問してください...',
        'search_button': '検索',
        'show_more_button': 'もっと見る',
        'clear_chat_button': 'チャットをクリア',
        'vector_search': 'ベクトル（意味的）',
        'text_search': 'テキスト（完全一致）',
        'database_stats': '📊 データベース統計',
        'total_events': '総イベント数',
        'total_buckets': '総バケット数',
        'last_updated': '最終更新',
        'example_queries': '💡 検索例',
        'example_queries_list': [
            'コーディングに費やした時間は？',
            'WhatsAppの使用時間は？',
            '最も使用しているアプリは？'
        ],
        'search_tips': '💡 検索のヒント',
        'search_tips_list': [
            '具体的なアプリ名を使用: "Cursor", "WhatsApp", "Chrome"',
            '期間を指定: "今日", "昨日", "今週"',
            '活動タイプで検索: "コーディング", "ブラウジング", "SNS"',
            '組み合わせて使用: "Cursor 昨日", "WhatsApp 今週"'
        ],
        'search_info': '🔍 **検索情報:**',
        'search_mode': '検索モード',
        'query': 'クエリ',
        'results_found': '検索結果',
        'search_time': '検索時間',
        'top_apps': 'トップアプリ',
        'app': 'アプリ',
        'duration': '時間',
        'time': '時刻',
        'title_col': 'タイトル',
        'page': 'ページ',
        'of': '/',
        'showing_events': 'イベント表示',
        'more_events': 'さらにイベント',
        'last_page': '最終ページ',
        'previous': '⬅️ 前へ',
        'next': '次へ ➡️',
        'clear_chat_confirm': 'チャット履歴をクリアしますか？',
        'yes': 'はい',
        'no': 'いいえ',
        'no_results': '一致するイベントが見つかりませんでした。',
        'similarity_threshold': '類似度しきい値',
        'max_results': '最大結果数',
        'time_filter': '期間フィルター',
        'bucket_filter': 'バケットフィルター'
    }
}

def t(key, *args):
    text = TRANSLATIONS.get(st.session_state.get('language', 'en'), TRANSLATIONS['en']).get(key, key)
    if args:
        return text.format(*args)
    return text

# --- Format Event Table (no window title, Nepal time, no seconds) ---
def format_event_table(events, start_index=0, page_size=25):
    table = f"| {t('time')} | {t('app')} | {t('title_col')} | {t('duration')} |\n|---|---|---|---|\n"
    for event in events[start_index:start_index+page_size]:
        data = event.get('data', {})
        app = data.get('app', '')
        title = data.get('title', '')
        timestamp = event.get('timestamp', event.get('event_timestamp', ''))
        # Convert to Nepal time and format as YYYY-MM-DD HH:MM
        try:
            utc_time = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            nepal_time = utc_time.astimezone(NEPAL_TZ)
            time_str = nepal_time.strftime('%Y-%m-%d %H:%M')
        except:
            time_str = timestamp[:16]
        duration = int(float(event.get('duration', 0)) // 60)
        table += f"| {time_str} | {app} | {title} | {duration} min |\n"
    return table

# --- Generate Response (Real, with stats) ---
def generate_response(query):
    import time as _time
    start = _time.time()
    client = st.session_state.client
    search_mode = st.session_state.get('search_mode', t('vector_search'))
    limit = st.session_state.get('max_results', 500)
    threshold = st.session_state.get('similarity_threshold', 0.7)
    events, search_info = client.search_events(query, search_mode=search_mode, limit=limit, similarity_threshold=threshold)
    elapsed = _time.time() - start
    st.session_state['current_events'] = events
    if not events:
        return t('no_results')
    # Top apps and total duration
    top_apps = {}
    total_duration = 0
    for e in events:
        app = e.get('data', {}).get('app', '')
        if app:
            top_apps[app] = top_apps.get(app, 0) + 1
        total_duration += float(e.get('duration', 0))
    top_apps_sorted = sorted(top_apps.items(), key=lambda x: x[1], reverse=True)
    top_apps_str = ', '.join(f"{app} ({count})" for app, count in top_apps_sorted[:5])
    total_duration_min = int(total_duration // 60)
    # Modern statistics panel
    st.markdown('---')
    st.markdown('#### 📊 Search Statistics')
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric(t('results_found'), len(events))
    with col2:
        st.metric(t('top_apps'), top_apps_str)
    with col3:
        st.metric(t('duration'), f"{total_duration_min} min")
    st.caption(f"{t('search_mode')}: {search_mode} | {t('search_time')}: {elapsed:.2f}s")
    st.caption(f"{t('search_info')} {search_info}")
    table = format_event_table(events, 0, st.session_state.page_size)
    return table

# --- Session State Initialization ---
if 'language' not in st.session_state:
    st.session_state.language = 'en'
if 'search_query' not in st.session_state:
    st.session_state['search_query'] = ''
if 'search_submitted' not in st.session_state:
    st.session_state['search_submitted'] = False
if 'chat_history' not in st.session_state:
    st.session_state['chat_history'] = []
if 'current_events' not in st.session_state:
    st.session_state['current_events'] = []
if 'current_page' not in st.session_state:
    st.session_state['current_page'] = 0
if 'page_size' not in st.session_state:
    st.session_state['page_size'] = 25
if 'search_mode' not in st.session_state:
    st.session_state['search_mode'] = t('vector_search')
if 'max_results' not in st.session_state:
    st.session_state['max_results'] = 500
if 'similarity_threshold' not in st.session_state:
    st.session_state['similarity_threshold'] = 0.7
if 'search_summary' not in st.session_state:
    st.session_state['search_summary'] = None
if 'time_filter' not in st.session_state:
    st.session_state['time_filter'] = 'All Time'
if 'bucket_filter' not in st.session_state:
    st.session_state['bucket_filter'] = 'All Buckets'
if 'search_info' not in st.session_state:
    st.session_state['search_info'] = ''
if 'last_processed_query' not in st.session_state:
    st.session_state['last_processed_query'] = ''
if 'client' not in st.session_state:
    st.session_state.client = ActivityWatchSupabaseClient()

# --- Dashboard Statistics ---
st.subheader(t('database_stats'))
try:
    buckets = st.session_state.client.get_buckets()
    total_events = 0
    for bucket in buckets:
        try:
            bucket_events = st.session_state.client.get_events_count(bucket['id'])
            total_events += bucket_events
        except:
            continue
    col1, col2 = st.columns(2)
    with col1:
        st.metric(t('total_events'), f"{total_events:,}")
    with col2:
        st.metric(t('total_buckets'), len(buckets))
    st.caption(t('last_updated') + f": {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
except Exception as e:
    st.error(f"Error loading stats: {e}")

# --- Sidebar ---
with st.sidebar:
    st.header('⚙️ Settings')
    language_icon = "🌐" if st.session_state.language == 'en' else "🇯🇵"
    language_select = st.selectbox(
        language_icon + ' ' + t('language_selector'),
        ['English', '日本語'],
        index=0 if st.session_state.language == 'en' else 1,
        key='language_select',
        label_visibility="visible"
    )
    if language_select != ('English' if st.session_state.language == 'en' else '日本語'):
        st.session_state.language = 'en' if language_select == 'English' else 'ja'
        st.rerun()

    st.markdown("---")
    search_mode = st.selectbox(
        t('search_mode_label'),
        [t('vector_search'), t('text_search')],
        index=0,
        key='search_mode_selector'
    )
    st.session_state.search_mode = search_mode
    st.markdown("---")
    similarity_threshold = st.slider(
        t('similarity_threshold'),
        min_value=0.0,
        max_value=1.0,
        value=0.7,
        step=0.1,
        key='similarity_threshold_slider'
    )
    st.session_state.similarity_threshold = similarity_threshold
    max_results = st.slider(
        t('max_results'),
        min_value=10,
        max_value=1000,
        value=500,
        step=10,
        key='max_results_slider'
    )
    st.session_state.max_results = max_results
    time_filter = st.selectbox(
        t('time_filter'),
        [t('all_time') if 'all_time' in TRANSLATIONS[st.session_state.language] else 'All Time',
         t('today') if 'today' in TRANSLATIONS[st.session_state.language] else 'Today',
         t('yesterday') if 'yesterday' in TRANSLATIONS[st.session_state.language] else 'Yesterday',
         t('this_week') if 'this_week' in TRANSLATIONS[st.session_state.language] else 'This Week',
         t('last_week') if 'last_week' in TRANSLATIONS[st.session_state.language] else 'Last Week',
         t('this_month') if 'this_month' in TRANSLATIONS[st.session_state.language] else 'This Month'],
        index=0,
        key='time_filter_selector'
    )
    st.session_state.time_filter = time_filter
    bucket_filter = st.selectbox(
        t('bucket_filter'),
        ['All Buckets'] + [b['id'] for b in st.session_state.client.get_buckets()],
        index=0,
        key='bucket_filter_selector'
    )
    st.session_state.bucket_filter = bucket_filter
    st.markdown("---")
    st.subheader(t('example_queries'))
    example_queries = t('example_queries_list')
    for i, query in enumerate(example_queries):
        if st.button(query, key=f"example_{i}"):
            st.session_state['search_query'] = query
            st.session_state['search_submitted'] = True
            st.rerun()
    st.subheader(t('search_tips'))
    search_tips = t('search_tips_list')
    for tip in search_tips:
        st.write(f"• {tip}")
    st.markdown("---")
    if st.button(t('clear_chat_button'), key='clear_chat_btn'):
        st.session_state['chat_history'] = []
        st.session_state['current_events'] = []
        st.session_state['current_page'] = 0
        st.session_state['search_summary'] = None
        st.session_state['last_processed_query'] = ''
        st.session_state['search_info'] = ''
        st.session_state['search_query'] = ''
        st.session_state['search_submitted'] = False
        st.rerun()

# --- Main Title ---
st.title(t('title'))

# --- Search Panel ---
st.markdown('---')
st.markdown('### 🔍 Search Panel')
with st.form('search_form', clear_on_submit=False):
    user_query = st.text_input(
        t('search_input_placeholder'),
        value=st.session_state['search_query'],
        placeholder=t('search_input_placeholder'),
        label_visibility='collapsed'
    )
    submitted = st.form_submit_button(t('search_button'))

if submitted:
    st.session_state['search_query'] = user_query
    st.session_state['search_submitted'] = True

if st.session_state.get('search_submitted', False):
    st.session_state['search_submitted'] = False
    # Create search summary (optional)
    search_summary = {
        'query': st.session_state['search_query'],
        'mode': st.session_state.search_mode,
        'similarity': f"{st.session_state.similarity_threshold:.1f}",
        'max_results': st.session_state.max_results,
        'time_filter': st.session_state.time_filter,
        'bucket': st.session_state.bucket_filter,
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }
    st.session_state.search_summary = search_summary
    st.session_state.current_page = 0
    st.session_state.chat_history.append({"role": "user", "content": st.session_state['search_query']})
    with st.chat_message("user"):
        st.markdown(st.session_state['search_query'])
    # HIDDEN IMMEDIATE ASSISTANT DISPLAY (can revert by restoring the block below)
    with st.spinner(t('loading')):
        response = generate_response(st.session_state['search_query'])
    st.session_state.chat_history.append({"role": "assistant", "content": response})
    st.session_state.last_processed_query = st.session_state['search_query']
    # To revert: replace the above with the previous 'with st.chat_message("assistant"):' block.

# --- Display chat history with pagination support ---
for i, message in enumerate(st.session_state.chat_history):
    with st.chat_message(message["role"]):
        is_last_assistant = (
            message["role"] == "assistant"
            and i == len(st.session_state.chat_history) - 1
            and st.session_state.current_events
            and len(st.session_state.current_events) > 0
        )
        if is_last_assistant:
            total_events = len(st.session_state.current_events)
            current_page = st.session_state.current_page
            page_size = st.session_state.page_size
            start_index = current_page * page_size
            end_index = min(start_index + page_size, total_events)
            remaining_events = total_events - end_index
            total_pages = (total_events + page_size - 1) // page_size
            current_page_num = current_page + 1
            st.markdown(f"**📊 {t('page')} {current_page_num} {t('of')} {total_pages} | {t('showing_events')} {start_index + 1}-{end_index} {t('of')} {total_events}**")
            current_content = format_event_table(st.session_state.current_events, start_index, page_size)
            st.markdown(current_content)
            col1, col2, col3 = st.columns([1, 1, 1])
            with col1:
                if current_page > 0:
                    if st.button(t('previous'), key=f"prev_page_{i}"):
                        st.session_state.current_page -= 1
                        st.rerun()
                else:
                    st.markdown(f"{t('previous')} (disabled)")
            with col2:
                st.markdown(f"**{t('page')} {current_page_num} {t('of')} {total_pages}**")
                if remaining_events > 0:
                    st.markdown(f"*{remaining_events} {t('more_events')}*")
                else:
                    st.markdown(f"*{t('last_page')}*")
            with col3:
                if remaining_events > 0:
                    if st.button(t('next'), key=f"next_page_{i}"):
                        st.session_state.current_page += 1
                        st.rerun()
                else:
                    st.markdown(f"{t('next')} (disabled)")
            # Compute statistics
            events = st.session_state.current_events
            # Top apps and total duration
            top_apps = {}
            total_duration = 0
            for e in events:
                app = e.get('data', {}).get('app', '')
                if app:
                    top_apps[app] = top_apps.get(app, 0) + 1
                total_duration += float(e.get('duration', 0))
            top_apps_sorted = sorted(top_apps.items(), key=lambda x: x[1], reverse=True)
            top_apps_str = ', '.join(f"{app} ({count})" for app, count in top_apps_sorted[:5])
            total_duration_min = int(total_duration // 60)
            st.markdown('---')
            st.markdown('#### 📊 ' + t('results_found'))
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric(t('results_found'), len(events))
            with col2:
                st.metric(t('top_apps'), top_apps_str)
            with col3:
                st.metric(t('duration'), f"{total_duration_min} min")
            st.caption(f"{t('search_mode')}: {st.session_state.search_mode} | {t('search_time')}: {''}")
            st.caption(f"{t('search_info')} {st.session_state.get('search_info', '')}")
        else:
            st.markdown(message["content"])

# --- Clear Chat Section ---
if st.session_state.chat_history and len(st.session_state.chat_history) > 0:
    st.markdown("---")
    st.markdown("### 🧹 " + t('clear_chat_button'))
    if st.button("🗑️ " + t('clear_chat_button'), key="clear_chat_section", use_container_width=True):
        st.session_state['chat_history'] = []
        st.session_state['current_events'] = []
        st.session_state['current_page'] = 0
        st.session_state['search_summary'] = None
        st.session_state['last_processed_query'] = ''
        st.session_state['search_info'] = ''
        st.session_state['search_query'] = ''
        st.session_state['search_submitted'] = False
        st.rerun()
