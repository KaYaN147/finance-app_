import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import json
import requests

# Настройка страницы
st.set_page_config(page_title="Учёт финансов", layout="wide", initial_sidebar_state="expanded")

# Список поддерживаемых валют
CURRENCIES = [
    'RUB', 'USD', 'EUR', 'CNY', 'GBP', 
    'VND', 'EGP', 'TRY', 'GEL'
]

# Словарь с символами валют
CURRENCY_SYMBOLS = {
    'RUB': '₽',
    'USD': '$',
    'EUR': '€',
    'CNY': '¥',
    'GBP': '£',
    'VND': '₫',
    'EGP': 'E£',
    'TRY': '₺',
    'GEL': '₾'
}

# Категории
EXPENSE_CATEGORIES = [
    'Продукты', 'Транспорт', 'Развлечения', 'Коммунальные платежи',
    'Одежда', 'Здоровье', 'Образование', 'Накопления', 'Другое'
]
INCOME_CATEGORIES = ['Зарплата', 'Подработка', 'Инвестиции', 'Другое']

# Функции для работы с данными
def get_exchange_rates(base_currency='RUB'):
    try:
        url = f"https://api.exchangerate-api.com/v4/latest/{base_currency}"
        response = requests.get(url)
        data = response.json()
        return data['rates']
    except:
        st.error("Ошибка при получении курсов валют")
        return {currency: 1.0 if currency == base_currency else 0.0 for currency in CURRENCIES}

def convert_amount(amount, from_currency, to_currency):
    if from_currency == to_currency:
        return amount
    rates = get_exchange_rates(from_currency)
    return amount * rates.get(to_currency, 0)

def format_amount(amount, currency=None):
    currency = currency or st.session_state.default_currency
    symbol = CURRENCY_SYMBOLS.get(currency, currency)
    if currency == 'VND':  # Для донга не используем копейки
        return f"{int(amount):,} {symbol}"
    return f"{amount:,.2f} {symbol}"

def load_data():
    if 'transactions_data' not in st.session_state:
        st.session_state.transactions_data = []
    
    df = pd.DataFrame(st.session_state.transactions_data)
    if not df.empty and 'Дата' in df.columns:
        df['Дата'] = pd.to_datetime(df['Дата'])
    if df.empty:
        df = pd.DataFrame(columns=['Дата', 'Тип', 'Категория', 'Сумма', 'Описание', 'Бюджет', 'Валюта'])
    return df

def save_data(df):
    st.session_state.transactions_data = df.to_dict('records')

def load_goals():
    if 'goals_data' not in st.session_state:
        st.session_state.goals_data = []
    return st.session_state.goals_data

def save_goals(goals):
    st.session_state.goals_data = goals

def export_to_csv(df):
    export_df = df.copy()
    export_df['Дата'] = export_df['Дата'].dt.strftime('%d.%m.%Y')
    export_df['Сумма'] = export_df.apply(
        lambda row: format_amount(abs(row['Сумма']), row.get('Валюта', st.session_state.default_currency)),
        axis=1
    )
    export_df.loc[df['Тип'] == 'Расход', 'Сумма'] = '-' + export_df.loc[df['Тип'] == 'Расход', 'Сумма']
    return export_df.to_csv(index=False, encoding='utf-8-sig').encode('utf-8-sig')

def delete_transaction(index):
    st.session_state.transactions = st.session_state.transactions.drop(index).reset_index(drop=True)
    save_data(st.session_state.transactions)

def edit_transaction(index, edited_data):
    for key, value in edited_data.items():
        st.session_state.transactions.at[index, key] = value
    save_data(st.session_state.transactions)

def export_all_data():
    data = {
        'transactions': st.session_state.transactions_data,
        'goals': st.session_state.goals_data,
        'settings': {
            'default_currency': st.session_state.default_currency
        }
    }
    return json.dumps(data, ensure_ascii=False, default=str)

def import_all_data(json_str):
    try:
        data = json.loads(json_str)
        st.session_state.transactions_data = data['transactions']
        st.session_state.goals_data = data['goals']
        st.session_state.default_currency = data['settings']['default_currency']
        return True
    except:
        return False # Инициализация состояния
if 'transactions' not in st.session_state:
    st.session_state.transactions = load_data()

if 'goals' not in st.session_state:
    st.session_state.goals = load_goals()

if 'default_currency' not in st.session_state:
    st.session_state.default_currency = 'RUB'

# Заголовок приложения
st.title('💰 Расширенный учёт финансов')

# Боковая панель
with st.sidebar:
    tab1, tab2, tab3, tab4 = st.tabs(["Добавить", "Бюджет", "Цели", "Настройки"])
    
    with tab1:
        st.header("Добавить транзакцию")
        date = st.date_input('Дата', datetime.now())
        trans_type = st.selectbox('Тип', ['Расход', 'Доход'])
        
        categories = INCOME_CATEGORIES if trans_type == 'Доход' else EXPENSE_CATEGORIES
        category = st.selectbox('Категория', categories)
        
        currency = st.selectbox('Валюта', CURRENCIES, index=CURRENCIES.index(st.session_state.default_currency))
        amount = st.number_input('Сумма', min_value=0.0, step=100.0)
        
        if currency != st.session_state.default_currency:
            converted_amount = convert_amount(amount, currency, st.session_state.default_currency)
            st.write(f"Будет сохранено как: {format_amount(converted_amount, st.session_state.default_currency)}")
        
        description = st.text_input('Описание')
        
        if st.button('Добавить транзакцию'):
            final_amount = amount if currency == st.session_state.default_currency else converted_amount
            new_transaction = pd.DataFrame([{
                'Дата': pd.to_datetime(date),
                'Тип': trans_type,
                'Категория': category,
                'Сумма': final_amount if trans_type == 'Доход' else -final_amount,
                'Описание': f"{description} ({amount} {currency})" if currency != st.session_state.default_currency else description,
                'Бюджет': 0,
                'Валюта': st.session_state.default_currency
            }])
            st.session_state.transactions = pd.concat(
                [st.session_state.transactions, new_transaction],
                ignore_index=True
            )
            save_data(st.session_state.transactions)
            st.success('Транзакция добавлена!')
            st.rerun()

    with tab2:
        st.header("Установить бюджет")
        category_budget = st.selectbox('Категория для бюджета', EXPENSE_CATEGORIES)
        budget_amount = st.number_input('Месячный бюджет', min_value=0.0, step=1000.0)
        if st.button('Установить бюджет'):
            mask = st.session_state.transactions['Категория'] == category_budget
            if not mask.any():
                new_row = pd.DataFrame([{
                    'Дата': pd.to_datetime(datetime.now()),
                    'Тип': 'Расход',
                    'Категория': category_budget,
                    'Сумма': 0,
                    'Описание': 'Установка бюджета',
                    'Бюджет': budget_amount,
                    'Валюта': st.session_state.default_currency
                }])
                st.session_state.transactions = pd.concat(
                    [st.session_state.transactions, new_row],
                    ignore_index=True
                )
            else:
                st.session_state.transactions.loc[mask, 'Бюджет'] = budget_amount
            save_data(st.session_state.transactions)
            st.success('Бюджет установлен!')

    with tab3:
        st.header("Управление целями")
        goal_name = st.text_input("Название цели")
        goal_amount = st.number_input("Необходимая сумма", min_value=0.0, step=1000.0)
        goal_deadline = st.date_input("Срок достижения")
        
        if st.button("Добавить цель"):
            new_goal = {
                "name": goal_name,
                "target_amount": goal_amount,
                "deadline": goal_deadline.strftime("%Y-%m-%d"),
                "current_amount": 0
            }
            st.session_state.goals.append(new_goal)
            save_goals(st.session_state.goals)
            st.success("Цель добавлена!")

    with tab4:
        st.header("Настройки")
        
        st.subheader("Основные настройки")
        new_default_currency = st.selectbox(
            'Основная валюта',
            CURRENCIES,
            index=CURRENCIES.index(st.session_state.default_currency)
        )
        if new_default_currency != st.session_state.default_currency:
            st.session_state.default_currency = new_default_currency
            st.success(f"Основная валюта изменена на {new_default_currency}")
        
        st.subheader("Резервное копирование")
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("Экспортировать все данные"):
                data = export_all_data()
                st.download_button(
                    "Скачать резервную копию",
                    data,
                    "finance_backup.json",
                    "application/json"
                )
        
        with col2:
            uploaded_file = st.file_uploader("Загрузить резервную копию", type=['json'])
            if uploaded_file is not None:
                content = uploaded_file.read().decode()
                if import_all_data(content):
                    st.success("Данные успешно восстановлены!")
                    st.rerun()
                else:
                    st.error("Ошибка при восстановлении данных") 
# Основная область
tab1, tab2, tab3, tab4 = st.tabs(["📊 Обзор", "📈 Аналитика", "📝 История", "🎯 Цели"])

with tab1:
    col1, col2, col3 = st.columns(3)
    
    with col1:
        total_balance = st.session_state.transactions['Сумма'].sum()
        st.metric('Общий баланс', format_amount(total_balance))
    
    with col2:
        income = st.session_state.transactions[
            st.session_state.transactions['Сумма'] > 0
        ]['Сумма'].sum()
        st.metric('Общий доход', format_amount(income))
    
    with col3:
        expenses = abs(st.session_state.transactions[
            st.session_state.transactions['Сумма'] < 0
        ]['Сумма'].sum())
        st.metric('Общие расходы', format_amount(expenses))

    if not st.session_state.transactions.empty:
        col1, col2 = st.columns(2)
        
        with col1:
            expenses_df = st.session_state.transactions[st.session_state.transactions['Сумма'] < 0]
            if not expenses_df.empty:
                fig_pie = px.pie(
                    expenses_df,
                    values='Сумма',
                    names='Категория',
                    title='Структура расходов'
                )
                st.plotly_chart(fig_pie, use_container_width=True)
        
        with col2:
            if len(st.session_state.transactions) > 1:
                daily_balance = st.session_state.transactions.groupby('Дата')['Сумма'].sum().cumsum()
                fig_line = px.line(
                    daily_balance,
                    title='Динамика баланса',
                    labels={'value': 'Баланс', 'Дата': 'Дата'}
                )
                st.plotly_chart(fig_line, use_container_width=True)

with tab2:
    if not st.session_state.transactions.empty:
        col1, col2 = st.columns(2)
        with col1:
            start_date = st.date_input('Начальная дата', 
                                    min(st.session_state.transactions['Дата']),
                                    key='analysis_start_date')
        with col2:
            end_date = st.date_input('Конечная дата', 
                                    max(st.session_state.transactions['Дата']),
                                    key='analysis_end_date')
        
        filtered_df = st.session_state.transactions[
            (st.session_state.transactions['Дата'] >= pd.to_datetime(start_date)) &
            (st.session_state.transactions['Дата'] <= pd.to_datetime(end_date))
        ]
        
        st.subheader('Анализ расходов по категориям')
        expenses_analysis = filtered_df[filtered_df['Сумма'] < 0].groupby('Категория').agg({
            'Сумма': ['sum', 'count']
        }).round(2)
        expenses_analysis.columns = ['Общая сумма', 'Количество транзакций']
        expenses_analysis['Общая сумма'] = expenses_analysis['Общая сумма'].apply(
            lambda x: format_amount(abs(x))
        )
        st.dataframe(expenses_analysis, use_container_width=True)
        
        if not filtered_df.empty:
            monthly_expenses = filtered_df[filtered_df['Сумма'] < 0].groupby(
                pd.Grouper(key='Дата', freq='M')
            )['Сумма'].sum().abs()
            
            if not monthly_expenses.empty:
                fig_monthly = px.bar(
                    monthly_expenses,
                    title='Расходы по месяцам',
                    labels={'value': 'Сумма расходов', 'Дата': 'Месяц'}
                )
                st.plotly_chart(fig_monthly, use_container_width=True)

with tab3:
    col1, col2, col3 = st.columns(3)
    with col1:
        type_filter = st.multiselect('Тип', ['Доход', 'Расход'], default=['Доход', 'Расход'])
    with col2:
        category_filter = st.multiselect('Категория', EXPENSE_CATEGORIES + INCOME_CATEGORIES)
    with col3:
        min_amount = st.number_input('Минимальная сумма', value=0.0, key='history_min_amount')

    filtered_history = st.session_state.transactions.copy()
    if type_filter:
        filtered_history = filtered_history[filtered_history['Тип'].isin(type_filter)]
    if category_filter:
        filtered_history = filtered_history[filtered_history['Категория'].isin(category_filter)]
    filtered_history = filtered_history[abs(filtered_history['Сумма']) >= min_amount]

    if not filtered_history.empty:
        st.write("### История транзакций")
        
        for index, row in filtered_history.sort_values('Дата', ascending=False).iterrows():
            with st.expander(f"{row['Дата'].strftime('%d.%m.%Y')} - {row['Категория']} - {format_amount(row['Сумма'])}"):
                edit_col1, edit_col2 = st.columns([3, 1])
                
                with edit_col1:
                    edited_date = st.date_input(
                        "Дата",
                        row['Дата'],
                        key=f"date_{index}"
                    )
                    edited_type = st.selectbox(
                        "Тип",
                        ['Доход', 'Расход'],
                        index=0 if row['Тип'] == 'Доход' else 1,
                        key=f"type_{index}"
                    )
                    edited_category = st.selectbox(
                        "Категория",
                        INCOME_CATEGORIES if edited_type == 'Доход' else EXPENSE_CATEGORIES,
                        index=(INCOME_CATEGORIES if edited_type == 'Доход' else EXPENSE_CATEGORIES).index(row['Категория']),
                        key=f"category_{index}"
                    )
                    edited_currency = st.selectbox(
                        "Валюта",
                        CURRENCIES,
                        index=CURRENCIES.index(row['Валюта'] if pd.notna(row['Валюта']) else 'RUB'),
                        key=f"currency_{index}"
                    )
                    edited_amount = st.number_input(
                        "Сумма",
                        value=abs(float(row['Сумма'])),
                        min_value=0.0,
                        key=f"amount_{index}"
                    )
                    edited_description = st.text_input(
                        "Описание",
                        value=row['Описание'],
                        key=f"desc_{index}"
                    )
                
                with edit_col2:
                    if st.button("Сохранить изменения", key=f"save_{index}"):
                        final_amount = edited_amount
                        if edited_currency != st.session_state.default_currency:
                            final_amount = convert_amount(edited_amount, edited_currency, st.session_state.default_currency)
                        
                        edited_data = {
                            'Дата': pd.to_datetime(edited_date),
                            'Тип': edited_type,
                            'Категория': edited_category,
                            'Сумма': final_amount if edited_type == 'Доход' else -final_amount,
                            'Описание': f"{edited_description} ({edited_amount} {edited_currency})" if edited_currency != st.session_state.default_currency else edited_description,
                            'Валюта': st.session_state.default_currency
                        }
                        edit_transaction(index, edited_data)
                        st.success("Изменения сохранены!")
                        st.rerun()
                    
                    if st.button("Удалить", key=f"delete_{index}"):
                        delete_transaction(index)
                        st.success("Транзакция удалена!")
                        st.rerun()

        col1, col2 = st.columns(2)
        with col1:
            if st.button('Экспортировать в CSV'):
                csv_data = export_to_csv(filtered_history)
                st.download_button(
                    "Скачать CSV",
                    csv_data,
                    "finance_export.csv",
                    "text/csv",
                    key='download_csv'
                )

with tab4:
    st.subheader("Мои финансовые цели")
    
    for idx, goal in enumerate(st.session_state.goals):
        col1, col2, col3 = st.columns([2,1,1])
        
        with col1:
            st.write(f"**{goal['name']}**")
            progress = (goal['current_amount'] / goal['target_amount']) * 100 if goal['target_amount'] > 0 else 0
            st.progress(min(progress/100, 1.0))
            
        with col2:
            st.write(f"Прогресс: {progress:.1f}%")
            st.write(f"Осталось: {format_amount(goal['target_amount'] - goal['current_amount'])}")
            
        with col3:
            contribution = st.number_input(
                "Внести средства",
                min_value=0.0,
                step=100.0,
                key=f"goal_{idx}"
            )
            if st.button("Внести", key=f"contribute_{idx}"):
                st.session_state.goals[idx]['current_amount'] += contribution
                save_goals(st.session_state.goals)
                
                new_transaction = pd.DataFrame([{
                    'Дата': pd.to_datetime(datetime.now()),
                    'Тип': 'Расход',
                    'Категория': 'Накопления',
                    'Сумма': -contribution,
                    'Описание': f"Вклад в цель: {goal['name']}",
                    'Бюджет': 0,
                    'Валюта': st.session_state.default_currency
                }])
                st.session_state.transactions = pd.concat(
                    [st.session_state.transactions, new_transaction],
                    ignore_index=True
                )
                save_data(st.session_state.transactions)
                st.success("Средства внесены!")
                st.rerun()