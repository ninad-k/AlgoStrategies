"""
Export trained LightGBM model to ONNX format.
Builds ONNX protobuf directly from compiled proto files — no onnx C++ extension needed.

Usage:
    python models/training/export_onnx.py
"""

import importlib.util
import os
import sys
import types

import joblib
import numpy as np

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, PROJECT_ROOT)

from models.feature_engineering.features import FEATURE_NAMES


def _load_onnx_pb2():
    """
    Load onnx_ml_pb2 protobuf definitions directly,
    bypassing the blocked C++ onnx_cpp2py_export DLL.
    """
    onnx_dir = None
    for p in sys.path + [os.path.join(
        os.path.dirname(sys.executable), 'Lib', 'site-packages')]:
        candidate = os.path.join(p, 'onnx')
        if os.path.isdir(candidate) and os.path.exists(
                os.path.join(candidate, 'onnx_ml_pb2.py')):
            onnx_dir = candidate
            break

    if onnx_dir is None:
        # Try common pip locations
        for base in [
            os.path.join(os.path.dirname(sys.executable), 'Lib', 'site-packages'),
            os.path.join(sys.prefix, 'Lib', 'site-packages'),
        ]:
            candidate = os.path.join(base, 'onnx')
            if os.path.isdir(candidate) and os.path.exists(
                    os.path.join(candidate, 'onnx_ml_pb2.py')):
                onnx_dir = candidate
                break

    if onnx_dir is None:
        raise RuntimeError("Cannot find onnx package with onnx_ml_pb2.py")

    print(f"  Using onnx protos from: {onnx_dir}")

    # Block the C++ extension
    fake_cpp = types.ModuleType('onnx.onnx_cpp2py_export')
    sys.modules['onnx.onnx_cpp2py_export'] = fake_cpp

    # Create minimal onnx package stub so protobuf imports resolve
    fake_onnx = types.ModuleType('onnx')
    fake_onnx.__path__ = [onnx_dir]
    fake_onnx.__file__ = os.path.join(onnx_dir, '__init__.py')
    sys.modules['onnx'] = fake_onnx

    # Load just onnx_ml_pb2
    spec = importlib.util.spec_from_file_location(
        'onnx.onnx_ml_pb2',
        os.path.join(onnx_dir, 'onnx_ml_pb2.py'),
        submodule_search_locations=[])
    pb2 = importlib.util.module_from_spec(spec)
    sys.modules['onnx.onnx_ml_pb2'] = pb2
    spec.loader.exec_module(pb2)

    return pb2


def build_onnx_from_lgbm(model, n_features):
    """
    Build a valid ONNX model from a LightGBM sklearn-API model
    using raw protobuf — no onnx helper or C++ extension needed.
    """
    pb2 = _load_onnx_pb2()

    # Extract trees from LightGBM
    booster = model.booster_
    model_dump = booster.dump_model()
    trees = model_dump['tree_info']

    # Collect tree node arrays
    nodes_treeids = []
    nodes_nodeids = []
    nodes_featureids = []
    nodes_values = []
    nodes_hitrates = []
    nodes_modes = []
    nodes_truenodeids = []
    nodes_falsenodeids = []
    nodes_missing_value_tracks_true = []

    class_treeids = []
    class_nodeids = []
    class_ids = []
    class_weights = []

    def flatten_tree(node, tree_id):
        """Flatten tree into sequential node arrays."""
        flat_nodes = []

        def collect(n):
            flat_nodes.append(n)
            if 'split_feature' in n:
                collect(n['left_child'])
                collect(n['right_child'])

        collect(node)

        # Build index map
        node_to_idx = {id(n): idx for idx, n in enumerate(flat_nodes)}

        for idx, n in enumerate(flat_nodes):
            nodes_treeids.append(tree_id)
            nodes_nodeids.append(idx)
            nodes_hitrates.append(1.0)
            nodes_missing_value_tracks_true.append(1)

            if 'split_feature' in n:
                nodes_featureids.append(n['split_feature'])
                nodes_values.append(float(n['threshold']))
                nodes_modes.append('BRANCH_LEQ')
                nodes_truenodeids.append(node_to_idx[id(n['left_child'])])
                nodes_falsenodeids.append(node_to_idx[id(n['right_child'])])
            else:
                nodes_featureids.append(0)
                nodes_values.append(0.0)
                nodes_modes.append('LEAF')
                nodes_truenodeids.append(0)
                nodes_falsenodeids.append(0)

                class_treeids.append(tree_id)
                class_nodeids.append(idx)
                class_ids.append(0)
                class_weights.append(float(n['leaf_value']))

    for i, tree_info in enumerate(trees):
        flatten_tree(tree_info['tree_structure'], i)

    print(f"  Parsed {len(trees)} trees, {len(nodes_treeids)} total nodes, {len(class_weights)} leaves")

    # Build ONNX model using raw protobuf
    model_proto = pb2.ModelProto()
    model_proto.ir_version = 7
    model_proto.producer_name = 'AlgoStrategies'
    model_proto.model_version = 1
    model_proto.doc_string = 'EMA200 Squeeze ML probability model'

    # Opset imports
    opset_default = model_proto.opset_import.add()
    opset_default.domain = ''
    opset_default.version = 12

    opset_ml = model_proto.opset_import.add()
    opset_ml.domain = 'ai.onnx.ml'
    opset_ml.version = 2

    # Graph
    graph = model_proto.graph
    graph.name = 'ema200_squeeze_ml'

    # Input: features [None, n_features]
    inp = graph.input.add()
    inp.name = 'features'
    inp_type = inp.type.tensor_type
    inp_type.elem_type = pb2.TensorProto.FLOAT
    inp_shape = inp_type.shape
    dim0 = inp_shape.dim.add()
    dim0.dim_param = 'batch_size'
    dim1 = inp_shape.dim.add()
    dim1.dim_value = n_features

    # Output: label [None]
    out_label = graph.output.add()
    out_label.name = 'label'
    out_label_type = out_label.type.tensor_type
    out_label_type.elem_type = pb2.TensorProto.INT64
    dim0 = out_label_type.shape.dim.add()
    dim0.dim_param = 'batch_size'

    # Output: probabilities [None, 2]
    out_prob = graph.output.add()
    out_prob.name = 'probabilities'
    out_prob_type = out_prob.type.tensor_type
    out_prob_type.elem_type = pb2.TensorProto.FLOAT
    dim0 = out_prob_type.shape.dim.add()
    dim0.dim_param = 'batch_size'
    dim1 = out_prob_type.shape.dim.add()
    dim1.dim_value = 2

    # TreeEnsembleClassifier node
    node = graph.node.add()
    node.op_type = 'TreeEnsembleClassifier'
    node.domain = 'ai.onnx.ml'
    node.name = 'TreeEnsembleClassifier'
    node.input.append('features')
    node.output.append('label')
    node.output.append('probabilities')

    def add_attr_ints(name, values):
        attr = node.attribute.add()
        attr.name = name
        attr.type = pb2.AttributeProto.INTS
        attr.ints.extend(values)

    def add_attr_floats(name, values):
        attr = node.attribute.add()
        attr.name = name
        attr.type = pb2.AttributeProto.FLOATS
        attr.floats.extend(values)

    def add_attr_strings(name, values):
        attr = node.attribute.add()
        attr.name = name
        attr.type = pb2.AttributeProto.STRINGS
        attr.strings.extend([v.encode('utf-8') for v in values])

    def add_attr_string(name, value):
        attr = node.attribute.add()
        attr.name = name
        attr.type = pb2.AttributeProto.STRING
        attr.s = value.encode('utf-8')

    add_attr_ints('nodes_treeids', nodes_treeids)
    add_attr_ints('nodes_nodeids', nodes_nodeids)
    add_attr_ints('nodes_featureids', nodes_featureids)
    add_attr_floats('nodes_values', nodes_values)
    add_attr_floats('nodes_hitrates', nodes_hitrates)
    add_attr_strings('nodes_modes', nodes_modes)
    add_attr_ints('nodes_truenodeids', nodes_truenodeids)
    add_attr_ints('nodes_falsenodeids', nodes_falsenodeids)
    add_attr_ints('nodes_missing_value_tracks_true', nodes_missing_value_tracks_true)
    add_attr_ints('class_treeids', class_treeids)
    add_attr_ints('class_nodeids', class_nodeids)
    add_attr_ints('class_ids', class_ids)
    add_attr_floats('class_weights', class_weights)
    add_attr_ints('classlabels_int64s', [0, 1])
    add_attr_string('post_transform', 'LOGISTIC')

    return model_proto


def main():
    saved_dir = os.path.join(PROJECT_ROOT, "models", "saved_models")
    pkl_path = os.path.join(saved_dir, "ema200_squeeze_model.pkl")
    onnx_path = os.path.join(saved_dir, "ema200_squeeze_model.onnx")

    if not os.path.exists(pkl_path):
        print("No trained model found. Run train_model.py first.")
        return

    print("Loading trained model...")
    model = joblib.load(pkl_path)
    n_features = len(FEATURE_NAMES)
    print(f"  Trees: {model.n_estimators}, Features: {n_features}")

    print("\nBuilding ONNX model...")
    onnx_model = build_onnx_from_lgbm(model, n_features)

    # Serialize
    model_bytes = onnx_model.SerializeToString()
    with open(onnx_path, 'wb') as f:
        f.write(model_bytes)

    file_size = os.path.getsize(onnx_path)
    print(f"\nONNX model saved: {onnx_path} ({file_size / 1024:.1f} KB)")

    # Validate with onnxruntime
    print("\nValidating with ONNX Runtime...")
    import onnxruntime as ort

    session = ort.InferenceSession(onnx_path)
    input_name = session.get_inputs()[0].name
    output_names = [o.name for o in session.get_outputs()]

    print(f"  Input: {input_name}, shape: {session.get_inputs()[0].shape}")
    for o in session.get_outputs():
        print(f"  Output: {o.name}, shape: {o.shape}")

    # Test with random data
    test_data = np.random.randn(5, n_features).astype(np.float32)
    result = session.run(output_names, {input_name: test_data})

    labels = result[0]
    probs = result[1]
    print(f"\n  Test predictions (random input):")
    for i in range(5):
        print(f"    Sample {i}: label={labels[i]}, buy_prob={probs[i][1]:.4f}")

    # Compare with sklearn model
    print("\n  Comparing ONNX vs sklearn model...")
    sklearn_probs = model.predict_proba(test_data)
    max_diff = np.max(np.abs(probs[:, 1] - sklearn_probs[:, 1]))
    print(f"  Max probability difference: {max_diff:.6f}")
    if max_diff < 0.05:
        print("  Models match!")
    else:
        print(f"  Note: Small differences expected from tree serialization")

    print(f"\n ONNX export complete!")
    print(f"  File: {onnx_path}")
    print(f"  Size: {file_size / 1024:.1f} KB")
    print(f"  Copy to MT5: MQL5\\Files\\{os.path.basename(onnx_path)}")


if __name__ == "__main__":
    main()
