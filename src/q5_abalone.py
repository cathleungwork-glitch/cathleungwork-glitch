#!/usr/bin/env python3
"""COMP7103 Assignment 1, Question 5.

Build a binary Mature label from the Abalone data and tune a decision tree.
Each step prints a labelled block so the four required screenshots stay separate.
"""

from pathlib import Path

import pandas as pd
from sklearn.model_selection import GridSearchCV, train_test_split
from sklearn.tree import DecisionTreeClassifier, export_text
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score

DATA_PATH = Path(__file__).resolve().parents[1] / "data" / "abalone.data"

# ----------------------------------------------------------------------
# Step 1. Read abalone.data and construct the new dataset.
# ----------------------------------------------------------------------
columns = [
    "Sex",
    "Length",
    "Diameter",
    "Height",
    "Whole weight",
    "Shucked weight",
    "Viscera weight",
    "Shell weight",
    "Rings",
]
raw = pd.read_csv(DATA_PATH, header=None, names=columns)
data = pd.DataFrame(
    {
        "Length": raw["Length"],
        "Diameter": raw["Diameter"],
        "Height": raw["Height"],
        "Whole weight": raw["Whole weight"],
        "Mature": (raw["Rings"] > 8).astype(int),
    }
)

print("===== Step 1 output =====")
print("Preview of the first 3 rows of the new dataset:")
print(data.head(3).to_string(index=True))
print(f"Number of rows: {len(data)}")
print(f"Number of columns: {data.shape[1]}")

# ----------------------------------------------------------------------
# Step 2. Split into training and testing data, ratio 8:2.
# ----------------------------------------------------------------------
features = ["Length", "Diameter", "Height", "Whole weight"]
X = data[features]
y = data["Mature"]
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42
)

# ----------------------------------------------------------------------
# Step 3. Tune DecisionTreeClassifier with GridSearchCV on training data.
#         Score is the F1-score of the positive class (Mature = 1).
# ----------------------------------------------------------------------
param_grid = {
    "criterion": ["gini", "entropy"],
    "max_depth": [3, 4, 5, 6, 7, 8, 9, 10],
}
search = GridSearchCV(
    estimator=DecisionTreeClassifier(random_state=42),
    param_grid=param_grid,
    scoring="f1",
    cv=5,
)
search.fit(X_train, y_train)

print("\n===== Step 2 and Step 3 output =====")
print(f"Training set size: {len(X_train)}")
print(f"Testing set size: {len(X_test)}")
print(f"Split ratio (train:test) = {len(X_train)}:{len(X_test)}")
print(f"Best parameters: {search.best_params_}")
print(f"Best cross-validated F1-score (Mature = 1): {search.best_score_:.4f}")

# ----------------------------------------------------------------------
# Step 4. Fit a decision tree with the selected parameters and print it.
# ----------------------------------------------------------------------
best_tree = DecisionTreeClassifier(random_state=42, **search.best_params_)
best_tree.fit(X_train, y_train)
tree_text = export_text(best_tree, feature_names=features, decimals=4)

print("\n===== Step 4 output =====")
print(f"Decision tree parameters: {search.best_params_}")
print("Decision tree (text):")
print(tree_text)

# ----------------------------------------------------------------------
# Step 5. Evaluate on the testing data for class Mature = 1.
# ----------------------------------------------------------------------
y_pred = best_tree.predict(X_test)
accuracy = accuracy_score(y_test, y_pred)
precision = precision_score(y_test, y_pred, pos_label=1)
recall = recall_score(y_test, y_pred, pos_label=1)
f1 = f1_score(y_test, y_pred, pos_label=1)

print("===== Step 5 output =====")
print(f"Accuracy: {accuracy:.4f}")
print(f"Precision (Mature = 1): {precision:.4f}")
print(f"Recall (Mature = 1): {recall:.4f}")
print(f"F1-score (Mature = 1): {f1:.4f}")
