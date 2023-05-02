# Youtube Sentiment Analysis

## Prelim Setup
import requests, sys, time, os, argparse
import googleapiclient.discovery
import os
import pandas as pd
import re
import demoji 
import shutil
from langdetect import detect 
from textblob.blob import TextBlob
from os import listdir
from os.path import isfile, join

output_dir = "static/data/output/"
output_dir_processed = "static/data/output/processed/"
output_dir_sentiments = "static/data/output/sentiments/"
output_dir_video_prior = "static/data/output/prior_video_processed/"
output_dir_sentiment_prior = "static/data/output/prior_sentiment_processed/"

# Any characters to exclude, generally these are things that become problematic in CSV files
unsafe_characters = ['\n', '"']

# List of simple to collect features
snippet_features = ["title", "publishedAt", "channelId", "channelTitle", "categoryId"]


### Get YouTube Data and Save it
def setup(api_path, code_path):
  with open(api_path, 'r') as file:
    api_key = file.readline()

  with open(code_path) as file:
    country_codes = [x.rstrip() for x in file]

  return api_key, country_codes

def prepare_feature(feature):
  # Removes any character from the unsafe character list and surrounds the whole item in quotes
  for ch in unsafe_characters:
    feature = str(feature).replace(ch, "")
  return f'"{feature}"'

def api_request(page_token, country_code, api_key):
  # Builds the URL and requests the JSON from it
  request_url = f"https://www.googleapis.com/youtube/v3/videos?part=id,statistics,snippet{page_token}chart=mostPopular&regionCode={country_code}&maxResults=50&key={api_key}"
  request = requests.get(request_url)
  if request.status_code  == 429:
    print("Temp-Banned due to excess request, please wait and continue later")
    sys.exit()
  return request.json()

def get_tags(tags_list):
  # Takes a list of tags, prepares each tag and joins them into a string by the pipe character
  return prepare_feature("|".join(tags_list))

def get_videos(items):
  lines = []
  for video in items:
    comments_disabled = False
    ratings_disabled = False

    # We can assume something is wrong with the video if it has no statistics, often this means it has been deleted
    # so we can just skip it
    if "statistics" not in video:
      continue

    # A full explanation of all these features can be found on the Github page for this project
    video_id = prepare_feature(video['id'])

    # Snippet and statistics are sub-dicts of video, containing the most useful info
    snippet = video['snippet']
    statistics = video['statistics']

    # This list contains allof the features in snippet that are 1 deep and require no special processing
    features = [prepare_feature(snippet.get(feature, "")) for feature in snippet_features]

    # The following are special case feature which require unique processing, or are not within the snippet dict
    description = snippet.get("description", "")
    thumbnail_link = snippet.get("thumnails", dict()).get("defaults", dict()).get("url", "")
    trending_date = time.strftime("%y.%d.%m")
    tags = get_tags(snippet.get("tags", ["[none"]))
    view_count = statistics.get("viewCount", 0)

    # THis may be unclear, essentially the way the API works is that if a video has comments or rating disabled
    # then it has no feature for it, thus if they don't exist in the stat dict we know they are disabled
    if 'likeCount' in statistics and 'dislikeCount' in statistics:
      likes = statistics['likeCount']
      dislikes = statistics['dislikeCount']
    else:
      ratings_disabled = True
      likes = 0
      dislikes = 0

    if 'commentCount' in statistics:
      comment_count = statistics['commentCount']
    else:
      comments_disabled = True
      comment_count = 0

    # Compiles all of the various bits of info into one consistently formatted line
    line = [video_id] + features + [prepare_feature(x) for x in [trending_date, tags, view_count, likes, dislikes,
                                                                 comment_count, thumbnail_link, comments_disabled,
                                                                 ratings_disabled, description]]

    lines.append("," .join(line))
  return lines

def get_pages(country_code, api_key, next_page_token="&"):
    country_data = []

    # Because the API uses page tokens (which are literally just the same function of numbers everywhere) it is much
    # more inconvenient to iterate over pages, but that is what is done here.
    while next_page_token is not None:
        # A page of data i.e. a list of videos and all needed data
        video_data_page = api_request(next_page_token, country_code, api_key)

        # Get the next page token and build a string which can be injected into the request with it, unless it's None,
        # then let the whole thing be None so that the loop ends after this cycle
        next_page_token = video_data_page.get("nextPageToken", None)
        next_page_token = f"&pageToken={next_page_token}&" if next_page_token is not None else next_page_token

        # Get all of the items as a list and let get_videos return the needed features
        items = video_data_page.get('items', [])
        country_data += get_videos(items)

    return country_data

def write_to_file(country_code, country_data):

    print(f"Writing {country_code} data to file...")

    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    with open(f"{output_dir}/{time.strftime('%y.%d.%m')}_{country_code}_videos.csv", "w+", encoding='utf-8') as file:
        for row in country_data:
            file.write(f"{row}\n")

def get_data(country_codes, header, api_key):
    for country_code in country_codes:
        country_data = [",".join(header)] + get_pages(country_code, api_key)
        write_to_file(country_code, country_data)

## Get YouTube Comments Based on Trending Videos
def get_data_file():
  return [x for x in os.listdir(output_dir) if "US" in x]

def read_data_file():
  df = []
  data_file = get_data_file()
  #print(data_file)
  for dataframe in data_file: 
    new_data = pd.read_csv(output_dir + dataframe, header=0)
    df.append(new_data.loc[(new_data['comments_disabled'] == False) & (new_data["comment_count"] >= 100)])
  return pd.concat(df)

def google_api(id):
  # Disable OAuthlib's HTTPS verification when running locally.
  # *DO NOT* leave this option enabled in production
  os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"

  api_service_name = "youtube"
  api_version = "v3"
  DEVELOPER_KEY = 'AIzaSyBnWvvv0myzWqfZptExcamY0osOtd9jDY8'

  youtube = googleapiclient.discovery.build(
      api_service_name, api_version, developerKey= DEVELOPER_KEY)
  
  request = youtube.commentThreads().list(
      part="id,snippet",
      maxResults=30,
      order="relevance",
      videoId=id
  )

  response = request.execute()

  print(response)
  return response

def create_df_author_comments(response):
  authorname = []
  comments = []
  videoid =[]

  for i in range(len(response["items"])):
    authorname.append(response["items"][i]["snippet"]["topLevelComment"]["snippet"]["authorDisplayName"])
    comments.append(response["items"][i]["snippet"]["topLevelComment"]["snippet"]["textOriginal"])
    videoid.append(response["items"][i]["snippet"]["topLevelComment"]["snippet"]["videoId"])
  df = pd.DataFrame(comments, index = [videoid, authorname], columns=["Comments"])
  return df

def get_comments():
  output = []
  video_ids = read_data_file()['video_id']
  
  for video_id in video_ids:
    try:
      data = google_api(video_id)
      output.append(data)
    except:
      continue

  return output

def combine_comments_into_df(output):
  return pd.concat([create_df_author_comments(video) for video in output])

## Clean Comments
def cleaning_comments(comment):
  comment = re.sub("[🤣|🤭|🤣|😁|🤭|❤️|💜|👍|🏴|😣|😠|😊|💪|🙏|🔥|🐥|🌟|😉|🌶️]+", '', comment)
  comment = re.sub("[0-9]+", "", comment)
  comment = re.sub("[\:|\@|\)|\*|\.|\$|\!|\?|\,|\%|\"]+", " ", comment)
  return comment

def cleaning_comments1(comment):
  comment = re.sub("[💁|🌾|😎|♥|🤷‍♂|😭]+", "", comment)
  comment = re.sub("[\(|\-|\”|\“|\#|\!|\/|\«|\»|\&]+", "" ,comment)
  return comment

def cleaning_comments3(comment):
  comment = re.sub("\n", " ", comment)
  comment = re.sub('[\'|🇵🇰|\;|\！]+', '', comment)
  return comment

def remove_non_english_comments(df):
  comment = df[df["Comments"].map(detect) != 'en']
  authors = [author for author in comment.index]
  df.drop(authors, inplace= True)
  return df

def remove_comments(df):
  # Checks for comments which has zero length in a dataframe
  zero_length_comments = df[(df["Comments"].map(len) == 0) | (df["Comments"].map(len) <= 4)]
  # taking all the indexes of the filtered comments in a list
  zero_length_comments_index = [ind for ind in zero_length_comments.index]
  # removing those rows from dataframe whose indexes matches
  df.drop(zero_length_comments_index, inplace = True)
  return df

## Get Sentiments
def find_polarity_of_single_comment(text):
   return  TextBlob(text).sentiment.polarity

def find_polarity_of_every_comment(df):  
  df['Polarity'] = df['Comments'].apply(find_polarity_of_single_comment)
  return df

def analysis_based_on_polarity(df, analysis):
  df['Analysis'] = df['Polarity'].apply(analysis)
  return df

def save_sentiment_data(country_data):
  print(f"Writing US sentiment data to file...")

  if not os.path.exists(output_dir_sentiments):
    os.makedirs(output_dir_sentiments)

  country_data.to_csv(output_dir_sentiments+time.strftime('%y.%d.%m')+'_US_sentiments.csv', encoding='utf-8', 
    sep='\t') 
        
## Data Cleanup 

def cleanup_folder():
  only_video_file = [f for f in listdir(output_dir_processed) if isfile(join(output_dir_processed, f))]
  only_sentiment_file = [f for f in listdir(output_dir_sentiments) if isfile(join(output_dir_sentiments, f))]
  if only_video_file: 
    shutil.move(output_dir_processed+only_video_file[0], output_dir_video_prior+only_video_file[0]) 
  if only_sentiment_file:
    shutil.move(output_dir_sentiments+only_sentiment_file[0], output_dir_sentiment_prior+only_video_file[0]) 

### move_process_file
def move_process_file():
  # path = get_data_file()[0]
  file_name = get_data_file()
  shutil.move(output_dir+get_data_file()[0], output_dir_processed+get_data_file()[0]) 

  

## Get Transcript
#!pip install youtube_transcript_api -q
# from youtube_transcript_api import YouTubeTranscriptApi
# YouTubeTranscriptApi.get_transcript('nOI67IDlNMQ')

def run_all():
  if not os.path.exists(output_dir):
    os.makedirs("static/data/output/")
  if not os.path.exists(output_dir_processed):
    os.makedirs("static/data/output/")
  if not os.path.exists(output_dir_sentiments):
    os.makedirs("static/data/output/sentiments/")
  if not os.path.exists(output_dir_video_prior):
    os.makedirs("static/data/output/prior_video_processed/")
  if not os.path.exists(output_dir_sentiment_prior):
    os.makedirs("static/data/output/prior_sentiment_processed/")

  cleanup_folder()   
  
  # Used to identify columns, currently hardcoded order
  header = ["video_id"] + snippet_features + ["trending_date", "tages", "view_count", "likes", "dislikes",
                                            "comment_count", "thumbnail_link", "comments_disabled",
                                            "ratings_disabled", "description"]
  
  api_key, country_codes = setup("static/data/api_key.txt", "static/data/country_codes.txt")
  get_data(country_codes, header, api_key)
  output = get_comments()
  df = combine_comments_into_df(output)
  df = df.reset_index(drop=False).rename(columns={"level_0":"Video_id", "level_1":"Author_name"})
  df = df.set_index("Author_name")

  df["Comments"] = df["Comments"].apply(cleaning_comments)
  df["Comments"] = df["Comments"].apply(cleaning_comments1)
  df['Comments'] = df["Comments"].apply(cleaning_comments3)
  df = df.applymap(lambda x: demoji.replace(x, ''))
  df = remove_comments(df)
  df = remove_non_english_comments(df)
  lower = lambda comment: comment.lower()
  df['Comments'] = df['Comments'].apply(lower)
  
  df = find_polarity_of_every_comment(df)
  # Analysis Based on Polarity
  analysis = lambda polarity: 'Positive' if polarity > 0 else 'Neutral' if polarity == 0 else 'Negative'
  df = analysis_based_on_polarity(df, analysis)
  save_sentiment_data(df)
  move_process_file()
  return True

if __name__=="__main__":
  run_all()
  