import streamlit as st
import matplotlib.pyplot as plt
import pandas as pd
import requests
import re
import seaborn as sns
from bs4 import BeautifulSoup
from urllib.parse import urlparse
from datetime import datetime

def text_to_num(text):
    # used to convert votecounts to usable integers
    dic = {'K': 1000, 'M': 1000000}
    if text[-1] in dic:
        num, mag = text[:-1], text[-1]
        return int(float(num) * dic[mag])
    else:
        return float(text)

def is_valid_imdb_url(url):
    url = url + 'episodes/?season='
    # regex to match proper url and endpoints
    url_pattern = r'^https://www\.imdb\.com/title/tt\d+/episodes/\?season=$'
    # check if url belongs to imdb
    parsed_url = urlparse(url)
    if not (bool(parsed_url.scheme) and bool(parsed_url.netloc)):
        return False

    # verify url matches pattern
    return re.match(url_pattern, url) is not None

def scrape_data(url):
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return response.text
    except requests.exceptions.HTTPError as e:
        st.error(f"HTTP Error: {e}")
    except requests.exceptions.RequestException as e:
        st.error(f"Error: {e}")
    except Exception as e:
        st.error(f"An unexpected error occurred: {e}")

def parse_data(html_data, url):
    # parse overall series data, e.g. rating, vote count, reviewcount
    soup = BeautifulSoup(html_data, 'html.parser')
    series_rating = soup.find('span', class_='sc-bde20123-1 cMEQkK').text.strip()
    if '.' in series_rating:
        series_rating = float(series_rating)
    else:
        series_rating = int(series_rating)
    series_votes = text_to_num(soup.find('div', class_='sc-bde20123-3 gPVQxL').text.strip())

    overall_series_data = [series_rating, series_votes]

    url = url + 'episodes/?season='
    season_tab_html = scrape_data(url)
    soup = BeautifulSoup(season_tab_html, 'html.parser')
    seasontabs = soup.find_all('li', {"data-testid" : 'tab-season-entry'})
    seasons = []
    for tab in seasontabs:
        try:
            season_number = int(tab.text.strip())
            seasons.append(season_number)
        except ValueError:
            print(f"Skipping non-integer season tab: {tab.text.strip()}")
    seasons = range(1, int(seasontabs[-1].text.strip()) + 1)
    show_name = soup.find('h2', class_='sc-a885edd8-9 dcErWY').text.strip()
    overall_series_data.append(show_name)

    # extract image poster url for display when parsing is done
    # use alt and class fields to ensure right image is grabbed 
    poster_tag = soup.find('img', {'alt': show_name, 'class': 'ipc-image'})
    poster_url = poster_tag['src'] if poster_tag else 'Image not found'
    
    # regular expressions
    epnum = re.compile(r'S[0-9]+\.E([0-9]+)')
    ratingmatch = re.compile(r'(\d+(?:\.\d+)?)')
    votesmatch = re.compile(r'\(([^)]*)\)')

    cumulative_episode_number = 0
    series_episode_data = []

    for season in seasons:
        season_html = scrape_data(url + str(season))
        season_soup = BeautifulSoup(season_html, 'html.parser')
        episodes = season_soup.find_all('div', class_='kyIRYf')

        for episode in episodes:
            # title found in div of class ipfc-title__text, strip to get rid of leading/trailing whitespace
            # this element includes both episode number and title- will be further separated
            title = episode.find('div', class_='ipc-title__text').text.strip()
            # take episode number from title string using regex, convert to int
            episode_number = int(epnum.sub('\\1', title.split(' ∙ ')[0]))
            # update cumulative episode number
            cumulative_episode_number += 1
            # grab title from string, split by dot
            title = title.split(' ∙ ')[1]
            # rating is located in the span of class ipc-rating-star, strip this like the title
            # try / except for future pending season/episode entries with no data: we don't want this and it'll just cause an error.
            try:
                rating = episode.find('span', class_='ipc-rating-star').text.strip()
            except AttributeError:
                break
            # find rating value using regex, first group found, convert to float
            rating_value = re.search(ratingmatch, rating).group(1)
            if '.' in rating_value:
                rating_value = float(rating_value)
            else:
                rating_value = int(rating_value)
            # find vote count from rating string using regex, first group found, convert to num from text
            votes = text_to_num(re.search(votesmatch, rating).group(1))\
            # airdate located in span with class fyhHWhz- strip whitespace, format to proper date notation and convert to datetime
            air_date = datetime.strptime(episode.find('span', class_='fyHWhz').text.strip(), r'%a, %b %d, %Y')
            # description located in div of class ipc-html-content-inner-div, strip whitespace from result
            description = episode.find('div', class_='ipc-html-content-inner-div').text.strip()

            # compile all final found and cleaned data into array, print and append to show (turn show into array of arrays)
            episode_data = [season, episode_number, cumulative_episode_number, title, air_date, rating_value, votes, description]
            series_episode_data.append(episode_data)

    return series_episode_data, overall_series_data, poster_url

def visualize_data(df, series_data, poster_url):
    show_name = series_data[2]
    # empty dataframe check
    if df.empty:
        st.error("No data available for visualization.")
        return
    
    # html to format the poster and title
    st.markdown(
        """
        <style>
        .container {
            display: flex;
        }
        .text {
            font-weight:700;
            font-size:75px;
            padding-left: 25px;
        }
        .logo-img {
            float:right;
        }
        </style>
        """,
        unsafe_allow_html=True
    )

    st.markdown(
        f"""
        <div class="container">
            <img class="logo-img" src="{poster_url}">
            <p class="text">{show_name}</p>
        </div>
        """,
        unsafe_allow_html=True
    )
    
    tab1, tab2, tab3, tab4 = st.tabs(["Graphs", "Highest/Lowest-Rated", "Quick Stats", "Raw Dataframe"])
    
    # all visualizations in one tab
    with tab1:
        st.header("Average Rating per Season")
        # visualization 1: average rating per season
        avg_rating_per_season = df.groupby('season')['rating_value'].mean().reset_index()
        plt.figure(figsize=(10, 6))
        sns.barplot(data=avg_rating_per_season, x='season', y='rating_value')
        plt.title(f'Average Rating per Season of {show_name}')
        plt.xlabel('Season')
        plt.ylabel('Average Rating')
        st.pyplot(plt)

        # clear current plot
        plt.clf()

        st.header("Ratings Distribution/Histogram")
        # visualization 2: ratings histogram
        plt.figure(figsize=(10, 6))
        sns.histplot(df['rating_value'], bins=20, kde=True)
        plt.title(f'Distribution of {show_name} Episode Ratings')
        plt.xlabel('Rating')
        plt.ylabel('Count')
        st.pyplot(plt)

        plt.clf()

        st.header("Overtime Ratings Trend")
        # visualization 3: episode ratings overtime
        plt.figure(figsize=(15,6))
        plt.grid(color='grey', linestyle='--', linewidth=0.5)

        max_rating = df['rating_value'].max()
        min_rating = df['rating_value'].min()

        plt.axhline(max_rating, color='green', label='Max', linewidth=0.8, linestyle='--')
        plt.axhline(min_rating, color='red', label='Min', linewidth=0.8, linestyle='--')
        plt.axhline(df['rating_value'].mean(), color='black', label='Average', linewidth=0.8, linestyle='--')
        sns.lineplot(data=df, x='cumulative_episode_number', y='rating_value')
        sns.scatterplot(data=df, x='cumulative_episode_number', y='rating_value')
        plt.xlim(0,df['cumulative_episode_number'].max()+2)
        plt.xlabel("Episode Number")
        plt.ylabel("Rating")
        plt.title(f"IMDb Rating Trend for {show_name}")
        plt.legend(loc='upper left', bbox_to_anchor=(1,1))
        st.pyplot(plt)

        plt.clf()

        st.header("Heatmap")
        # visualization 4: ratings heatmap
        pivot_df = df.pivot_table(index="season", columns="episode_number", values="rating_value")
        plt.figure(figsize=(10,9))
        ax = sns.heatmap(pivot_df, annot=True)

        ax.set_xlabel('Episode Number')
        ax.set_ylabel('Season')

        # set the title
        ax.set_title(f'Ratings per {show_name} episode')

        ax.tick_params(axis='both', which='both', length=0)
        ax.set_xticklabels(ax.get_xticklabels(), rotation=0) 
        ax.set_yticklabels(ax.get_yticklabels(), rotation=0)

        st.pyplot(plt)
        plt.clf()

    # top/bottom episodes
    with tab2:
        st.header("Highest/Lowest-Rated")
        # vis. 5, table 1: top 10 highest-rated episodes
        st.subheader(f'Top 10 {show_name} episodes')
        top_10 = df.nlargest(n=10, columns=['rating_value'])[['season', 'episode_number', 'title', 'rating_value']]
        top_10['rating_value'] = top_10['rating_value'].astype(float).round(2).astype(str)
        st.table(top_10)

        # vis 6, table 2: bottom 10 lowest-rated episodes
        st.subheader(f'Bottom 10 {show_name} episodes')
        bottom_10 = df.nsmallest(n=10, columns=['rating_value'])[['season', 'episode_number', 'title', 'rating_value']]
        bottom_10['rating_value'] = bottom_10['rating_value'].astype(float).round(2).astype(str)
        st.table(bottom_10)

    with tab3:
        # overall_series_data = [series_rating, series_votes, series_reviews]
        st.header("Quick Stats")
        st.markdown(f'Series rating: {series_data[0]}')
        st.markdown(f'Series vote count: {series_data[1]}')
        col1, col2 = st.columns(2)
        # average episode rating, std. dev, median, range
        with col1:
            st.subheader('Ratings')
            st.markdown(f'Average episode rating: {df['rating_value'].mean():.2f}')
            st.markdown(f'Standard deviation: {df['rating_value'].std():.2f}')
            st.markdown(f'Median episode rating: {df['rating_value'].median():.2f}')
            rating_range = df['rating_value'].max() - df['rating_value'].min()
            st.markdown(f'Range of episode ratings: {rating_range:.2f}')
        with col2:
            st.subheader('Votes')
            st.markdown(f'Average votecount: {df['votes'].mean():.2f}')
            st.markdown(f'Standard deviation: {df['votes'].std():.2f}')
            st.markdown(f'Median vote count: {df['votes'].median():.2f}')
            vote_range = df['votes'].max() - df['votes'].min()
            st.markdown(f'Range of vote counts: {vote_range:.2f}')       

    # raw dataframe for viewing, searching and downloading
    with tab4:
        st.header("Dataframe")
        st.dataframe(df)


# sidebar for input
st.sidebar.title('IMDb Data Analysis')

st.sidebar.markdown("""
    Enter the IMDb URL in the following format:\n
    `https://www.imdb.com/title/[title_id]/`\n
    Replace `[title_id]` with the specific title id for the show.
""")

url_input = st.sidebar.text_input(f'Enter IMDb URL')
scrape_button = st.sidebar.button('Scrape Data')

if scrape_button:
    # url_input = url_input + 'episodes/?season='
    print(url_input)
    if is_valid_imdb_url(url_input):
        with st.spinner('Scraping...'):
            html_data = scrape_data(url_input)
            if html_data:
                processed_data = parse_data(html_data, url_input)
                st.toast('Data scraped!', icon="📺")
                df = pd.DataFrame(processed_data[0],columns=["season", "episode_number", "cumulative_episode_number", "title", "air_date", "rating_value", "votes", "description"])
                visualize_data(df,processed_data[1],processed_data[2])
            else:
                st.error('Failed to scrape data.')
    else:
        st.error('Invalid URL. Please enter a valid URL.')
