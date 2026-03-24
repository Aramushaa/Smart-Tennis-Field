import numpy as np
from onnxruntime import SessionOptions, InferenceSession, ExecutionMode, GraphOptimizationLevel
from numpy import load, argmax, expand_dims
from typing import Callable, List


def softmax(x, alpha=0.3):
    print(x)
    return np.exp(alpha*x) / sum(np.exp(alpha*x))


class InferenceEngine:
    def __init__(self, model_path, activity_labels):
        self.session = None
        self.model_path = model_path
        self.activity_labels: List = activity_labels
        self.cb: Callable = self.default_callback

    def initialize(self):
        session_options = SessionOptions()
        session_options.execution_mode = ExecutionMode.ORT_SEQUENTIAL
        session_options.graph_optimization_level = GraphOptimizationLevel.ORT_ENABLE_ALL
        session_options.inter_op_num_threads = 1
        session_options.intra_op_num_threads = 1
        session_options.enable_mem_pattern = True
        session_options.enable_cpu_mem_arena = False
        session_options.enable_mem_reuse = True
        # Load the model
        self.session = InferenceSession(self.model_path, sess_options=session_options)

    def execute_inference(self, accelerometer, gyroscope):
        data = np.array(
            [accelerometer['x'], accelerometer['y'], accelerometer['z'], gyroscope['x'], gyroscope['y'],
             gyroscope['z']])
        inference_inputs = {self.session.get_inputs()[0].name: expand_dims(data.swapaxes(1, 0), 1)}
        output = self.session.run(None, inference_inputs)

        total_output_activity = sum(output[0], 0)
        print(total_output_activity)
        prob_class = softmax(sum(output[0], 0)[0]) * 100
        prob_class = np.round(prob_class, decimals=2)
        ##### IF per verificare la soglia tra le probabilità
        pred_class = argmax(total_output_activity) # argmax(sum(output[0], 0))
        print(f"Predicted class: {self.activity_labels[pred_class]} - Probabilities: {prob_class}")

        self.cb(self.activity_labels[pred_class])

    def default_callback(self, activity):
        print(activity)
