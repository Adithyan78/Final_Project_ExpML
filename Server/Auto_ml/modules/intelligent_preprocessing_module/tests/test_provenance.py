from Server.Auto_ml.modules.intelligent_preprocessing_module.preprocessing_module import PreprocessingEngine


def test_every_output_feature_has_provenance_entry(titanic_split, titanic_profile):
    X_train, X_test, y_train, y_test = titanic_split
    engine = PreprocessingEngine()
    result = engine.fit_transform(X_train, y_train, titanic_profile)

    provenance_features = {p["output_feature"] for p in result["feature_provenance"]}
    assert provenance_features == set(engine.all_feature_names_)


def test_sex_onehot_features_map_back_to_sex(titanic_split, titanic_profile):
    X_train, X_test, y_train, y_test = titanic_split
    engine = PreprocessingEngine()
    result = engine.fit_transform(X_train, y_train, titanic_profile)

    sex_prov = [p for p in result["feature_provenance"] if p["source_column"] == "Sex"]
    assert len(sex_prov) >= 1
    for p in sex_prov:
        assert p["transformation"] == "one_hot"
        assert p["output_feature"].startswith("Sex")


def test_age_provenance_records_impute_and_scale_chain(titanic_split, titanic_profile):
    X_train, X_test, y_train, y_test = titanic_split
    engine = PreprocessingEngine()
    result = engine.fit_transform(X_train, y_train, titanic_profile)

    age_prov = next(p for p in result["feature_provenance"] if p["output_feature"] == "Age")
    assert age_prov["source_column"] == "Age"
    assert age_prov["transformation"] == "impute_median+standard_scale"


def test_dropped_columns_produce_no_provenance_entries(titanic_split, titanic_profile):
    X_train, X_test, y_train, y_test = titanic_split
    engine = PreprocessingEngine()
    result = engine.fit_transform(X_train, y_train, titanic_profile)

    for dropped in ("PassengerId", "Name", "Cabin"):
        assert not any(p["source_column"] == dropped for p in result["feature_provenance"])
