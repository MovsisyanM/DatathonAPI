from flask import Flask, request, jsonify, Response

app = Flask(__name__)

reference_list = [1, 0, 1, 1, 0, 0, 1, 0]


@app.route('/', methods=["GET"])
def instructions():
    return jsonify({'message': '''To use this API, make a POST request to the "/d2023-accuracy"
        endpoint with a JSON object containing a key `predictions` and value of a list of model outputs. 
        Don\'t mix the order of the data to avoid bad accuracy scores'''})

@app.route('/d2023', methods=['POST'])
def calculate_accuracy():
    """"""
    data = request.get_json()
    print(data)
    
    if "predictions" not in data.keys():
        return Response("Please specify `predictions` in the request.", status=400)
    
    if len(data["predictions"]) != len(reference_list):
        return Response("""The length of the list `predictions` doesn't match the evaluation data length.
                        Make sure that the """)
        
    submitted_list = data['predictions']
    correct_count = 0
    for i in range(len(reference_list)):
        if submitted_list[i] == reference_list[i]:
            correct_count += 1
    accuracy = correct_count / len(reference_list)
    return jsonify({'accuracy': accuracy})

if __name__ == '__main__':
    app.run()