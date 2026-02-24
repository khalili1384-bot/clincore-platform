import os
import pandas as pd

from src.clincore.mcare_engine.mcare_sqlite_engine_v6_1 import score_case, load_params

def main():
    db_path = os.getenv("REPERTORY_DB_PATH", "src/clincore/mcare_engine/data/synthesis.db")
    cfg_path = "src/clincore/mcare_engine/mcare_config_v6_1.json"

    params = load_params(cfg_path)

    # نمونه کیس: باید symptom_id و weight داشته باشد
    # symptom_id ها را از syntree انتخاب کن (مثل 13401754, 13401755 ...)
    case_df = pd.DataFrame([
        {"symptom_id": 13401754, "weight": 1.0},
        {"symptom_id": 13401755, "weight": 1.0},
    ])

    # tags اگر ساختار خاصی دارد فعلا خالی میگذاریم
    tags = {}

    top_n = 10
    case_type = "auto"   # auto | mind_dominant | constitution | mixed
    course = "acute"     # None نباشد چون .lower() میزند

    df = score_case(
        db_path=db_path,
        case_df=case_df,
        tags=tags,
        params=params,
        top_n=top_n,
        case_type=case_type,
        course=course,
    )

    print("\n=== ENGINE OUTPUT ===\n")
    print(df.head(top_n))
    print("\nColumns:", list(df.columns))

if __name__ == "__main__":
    main()
