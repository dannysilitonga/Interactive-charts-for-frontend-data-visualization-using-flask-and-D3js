#import sys
#sys.path.append("data")

from flask import Flask, jsonify, render_template
from static.data.get_youtube import run_all
import pandas as pd
import numpy as np
from os import listdir
from os.path import isfile, join

app = Flask(__name__)

# Reading data
data_df = pd.read_csv("static/data/churn_data.csv")
churn_df = data_df[(data_df["Churn"]=="Yes").notnull()]

output_path = './static/data/output/'
file_name = [f for f in listdir(output_path+'sentiments/') if isfile(join(output_path+'sentiments/', f))]
sentiments = pd.read_csv(output_path+'sentiments/'+file_name[0], header=0, sep='\t', on_bad_lines='skip',
                             engine='python')

@app.route('/')
def index():
    return render_template('index.html')

def calculate_percentage(val, total):
    """Calculate the percentage of a value over a total"""
    percent = np.round((np.divide(val, total) * 100), 2)
    return percent 

@app.route('/get_youtube_data')
def get_youtube_data():
    run_all()
    print("Youtube data has been extracted and process")
    return("nothing")

@app.route('/get_piechart_youtube')
def get_piechart_data_youtube():
    output_path = './static/data/output/'
    file_name = [f for f in listdir(output_path+'sentiments/') if isfile(join(output_path+'sentiments/', f))]
    sentiments = pd.read_csv(output_path+'sentiments/'+file_name[0], header=0, sep='\t', on_bad_lines='skip',
                             engine='python')
    sentiment_count = sentiments.groupby("Analysis").aggregate("count")['Comments']
    total_rows = sentiments.shape[0]
    shares = {}
    shares['Negative'] = sentiment_count['Negative']/total_rows * 100
    shares['Neutral'] = sentiment_count['Neutral']/total_rows * 100
    shares['Positive'] = sentiment_count['Positive']/total_rows * 100
    return shares

#@app.route('/get_piechart_data')
#def get_piechart_data():
#    shares = get_piechart_data_youtube()
#    return jsonify(shares)

def data_creation(data, percent, class_labels, group=None):
    for index, item in enumerate(percent):
        data_instance = {}
        data_instance['category'] = class_labels[index]
        data_instance['value'] = item
        data_instance['group'] = group
        data.append(data_instance)

@app.route('/get_piechart_data')
def get_piechart_data():
    contract_labels = ['Negative', 'Neutral', 'Positives']
    _ = sentiments.groupby('Analysis').size().values
    class_percent = calculate_percentage(_, np.sum(_)) #Getting the value counts and total 

    piechart_data = []
    data_creation(piechart_data, class_percent, contract_labels)
    return jsonify(piechart_data)


#@app.route('/get_piechart_data')
#def get_piechart_data():
#    contract_labels = ['Month-to-month', 'One year', 'Two year']
#    _ = churn_df.groupby('Contract').size().values
#    class_percent = calculate_percentage(_, np.sum(_)) #Getting the value counts and total 

#    piechart_data = []
#    data_creation(piechart_data, class_percent, contract_labels)
#    return jsonify(piechart_data)




@app.route('/get_barchart_data')
def get_barchart_data():
    # tenure_labels = ['0-9', '10-19', '20-29', '30-39', '40-49', '50-59', '60-69', '70-79']
    # churn_df['tenure_group'] = pd.cut(churn_df.tenure, range(0, 81, 10), labels=tenure_labels)
    # select_df = churn_df[['tenure_group', 'Contract']]
    # contract_month = select_df[select_df['Contract']=='Month-to-month']
    # contract_one = select_df[select_df['Contract']=='Two year']
    # contract_two = select_df[select_df['Contract']=='Two year']
    # _ = contract_month.groupby('tenure_group').size().values
    # mon_percent = calculate_percentage(_, np.sum(_))
    # _ = contract_one.groupby('tenure_group').size().values
    # one_percent = calculate_percentage(_, np.sum(_))
    # _ = contract_two.groupby('tenure_group').size().values
    # two_percent = calculate_percentage(_, np.sum(_))
    # _ = select_df.groupby('tenure_group').size().values
    # all_percent = calculate_percentage(_, np.sum(_))

    
    select_df = sentiments[['Video_id', 'Analysis']]
    select_df = select_df[:65]
    contract_month = select_df[select_df['Analysis']=='Negative']
    contract_one = select_df[select_df['Analysis']=='Neutral']
    contract_two = select_df[select_df['Analysis']=='Positive']
    
    _ = contract_month.groupby('Video_id').size().values 
    mon_percent = calculate_percentage(_, np.sum(_))
    tenure_labels_neg = [x for x in contract_month.groupby('Video_id').size().index]
    
    _ = contract_one.groupby('Video_id').size().values
    one_percent = calculate_percentage(_, np.sum(_))
    tenure_labels_neutral = [x for x in contract_one.groupby('Video_id').size().index]
    
    _ = contract_two.groupby('Video_id').size().values
    all_percent = calculate_percentage(_, np.sum(_))
    tenure_labels_pos = [x for x in contract_two.groupby('Video_id').size().index]
    

    barchart_data = []
    data_creation(barchart_data, all_percent, tenure_labels_pos, "Positive")
    data_creation(barchart_data, one_percent, tenure_labels_neutral, "Neutral")
    data_creation(barchart_data, mon_percent, tenure_labels_neg, "Positive")
    print(len(tenure_labels_neg))
    print(len(tenure_labels_pos))
    print(len(tenure_labels_neutral))

    # barchart_data = []
    # data_creation(barchart_data, all_percent, tenure_labels, "All")
    # data_creation(barchart_data, mon_percent, tenure_labels, "Month-to-month")
    # data_creation(barchart_data, one_percent, tenure_labels, "One year")
    # data_creation(barchart_data, two_percent, tenure_labels, "Two year")
    return jsonify(barchart_data)

if __name__ == '__main__':
    app.run(debug=True)

