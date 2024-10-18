from flask import Flask, jsonify, request
from flask_cors import CORS
from pathlib import Path
import pandas as pd
import numpy as np
import joblib
import ast
import json

app = Flask(__name__)
CORS(app)

with open(Path('Data') / 'disease_to_specialization.json') as f:
    disease_to_specialization = json.load(f)

diseases = pd.read_csv(Path('Data') / 'diseases.csv').set_index('Disease')
doctors = pd.read_csv(Path('Data') / 'sharp_medical_professionals.csv')
modelfp = Path('Models') / 'LogisticRegressionModel.pkl'

def get_disease(prediction, probability):
    disease = diseases.loc[prediction].to_dict()
    disease['name'] = prediction
    disease['probability'] = float(probability)
    
    disease['precautions'] = [value for key, value in disease.items() if 'Precaution' in key]
    disease = {key: value for key, value in disease.items() if 'Precaution' not in key}
    
    disease['treatments'] = [value for key, value in disease.items() if 'Treatment' in key]
    disease = {key: value for key, value in disease.items() if 'Treatment' not in key}
    return disease

@app.route('/api/predict/disease', methods=['POST'])
def predict_disease():
    
    data = request.get_json()
    model = joblib.load(open(modelfp, 'rb'))
    
    if not hasattr(model, 'predict'): return jsonify({'error': 'Not a valid model'}), 400
    
    X = np.array(data).reshape(1, -1)
    Y_probs = model.predict_proba(X)
    
    labels = model.classes_
    top_preds = np.argsort(Y_probs, axis=1)[:, -3:][:, ::-1]

    predictions = [{'prediction': labels[top_preds[0, j]], "probability": Y_probs[0, top_preds[0, j]]} for j in range(3)]
    diseases = [get_disease(**prediction) for prediction in predictions]
    
    return jsonify(diseases), 200

def get_specialty_score(specialties, disease_inputs):
    score = 0
    for specialty in specialties:
        for disease in disease_inputs:
            if specialty.lower() == disease_to_specialization[disease['disease']]:
                score += disease['probability']
    return score

@app.route('/api/predict/doctor', methods=['POST'])
def predict_doctor():
    disease_inputs = request.get_json()
    
    cleaned_doctors = doctors.copy()
    cleaned_doctors['Location'] = doctors['Location'].transform(ast.literal_eval)
    cleaned_doctors['Specialty'] = doctors['Specialty'].transform(ast.literal_eval)
    cleaned_doctors['Phone Number'] = doctors['Phone Number'].transform(ast.literal_eval)
    
    scores = cleaned_doctors['Specialty'].apply(lambda x: get_specialty_score(x, disease_inputs))
    with_scores = cleaned_doctors.assign(Score = scores)

    only_positive_scores = with_scores.query('Score > 0').sort_values('Score', ascending = False)
    cleaned_dict = only_positive_scores.drop('Unnamed: 0', axis=1).fillna(-1).to_dict('records')
    
    print(cleaned_dict)
    return jsonify(cleaned_dict), 200

if __name__ == '__main__':
    app.run(debug=True)