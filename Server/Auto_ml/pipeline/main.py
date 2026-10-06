from Server.Auto_ml.modules.Dataset_Analyzer_module.Dataset_analyzer import (
    analyze_dataset,
    save_profile,
)

from Server.Auto_ml.modules.intelligent_preprocessing_module.Main import (
    run_preprocessing,
)


def main():

    dataset_path = dataset_path = r"D:\FYP_Auto_ML\Server\Auto_ml\modules\Dataset_Analyzer_module\adult.csv"
    target_column = "income"

    # ==========================================
    # MODULE 1: DATASET ANALYZER
    # ==========================================

    profile = analyze_dataset(
        dataset_path,
        target_column=target_column,
    )

    profile_path = "D:\FYP_Auto_ML\Server\Auto_ml\modules\Dataset_Analyzer_module/dataset_profile.json"

    save_profile(
        profile,
        profile_path,
    )

    # ==========================================
    # MODULE 2: INTELLIGENT PREPROCESSING
    # ==========================================

    run_preprocessing(
        dataset_path=dataset_path,
        profile_path=profile_path,
        target_column=target_column,
    )


if __name__ == "__main__":
    main()