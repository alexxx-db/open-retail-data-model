# ============================================================
# ORDM · Synthetic data · Customer domain generator
# Version: v1_mvm
# Generated: 2026-06-09
# LLM-generated: true (maintainer-reviewed before release)
# Last reviewed: 2026-06-09
# ============================================================
# Populates the canonical-core customer tables (profile, address,
# contact, consent, account) with realistic-but-synthetic, deterministic
# data so ORDM deploys and demos without any real customer data.
#
# Engine: dbldatagen for the master entities (profile, account), PySpark
# for the children. Children are built in PySpark — not dbldatagen —
# because each child's surrogate FK (profile_sk) must reference the
# IDENTITY value Delta assigned when profile was written, which is only
# knowable after the parent is materialized.
#
# Guardrails:
#   * No hardcoded catalog/schema/URL — read from job params / widgets.
#   * Tables must already exist (DDL deploy runs first); this only inserts.
#   * Generated values stay within the enum/ISO/GS1 domains declared in
#     the table DDL comments.
#
# Run as a Databricks notebook task (notebook_path: this file) with
# parameters: catalog, customer_schema, num_profiles, num_accounts, seed, mode.
# ============================================================

import os
import sys

import dbldatagen as dg
from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.sql.window import Window

try:
    from _common import RECORD_SOURCE, get_param, _pick, _frac, _count_1_to_max, _write
except ImportError:  # ensure sibling modules are importable when run as a notebook
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from _common import RECORD_SOURCE, get_param, _pick, _frac, _count_1_to_max, _write

# ------------------------------------------------------------
# Column contracts — MUST match the table DDL (minus IDENTITY *_sk).
# These drive the INSERT column lists and are checked against the DDL
# by tests/test_customer_model.py.
# ------------------------------------------------------------
PROFILE_COLUMNS = [
    "profile_id", "name_prefix", "first_name", "middle_name", "last_name",
    "name_suffix", "date_of_birth", "gender", "preferred_language_code",
    "nationality_country_code", "loyalty_id", "household_id",
    "customer_status", "enrollment_date", "effective_from_date",
    "effective_to_date", "current_flag", "record_source", "load_timestamp",
]
ADDRESS_COLUMNS = [
    "address_id", "profile_sk", "profile_id", "address_type",
    "address_line_1", "address_line_2", "city", "state_province",
    "postal_code", "country_code", "latitude", "longitude", "is_primary",
    "address_status", "effective_from_date", "effective_to_date",
    "current_flag", "record_source", "load_timestamp",
]
CONTACT_COLUMNS = [
    "contact_id", "profile_sk", "profile_id", "contact_type",
    "contact_value", "country_calling_code", "is_primary", "is_verified",
    "verified_timestamp", "contact_status", "record_source",
    "load_timestamp", "updated_timestamp",
]
CONSENT_COLUMNS = [
    "consent_id", "profile_sk", "profile_id", "consent_type",
    "consent_status", "legal_basis", "capture_channel",
    "disclosure_version", "valid_from_timestamp", "valid_to_timestamp",
    "current_flag", "record_source", "load_timestamp",
]
ACCOUNT_COLUMNS = [
    "account_id", "account_name", "account_type", "registration_number",
    "tax_id", "gln", "industry_classification_code", "parent_account_id",
    "primary_contact_profile_id", "account_status", "credit_limit_amount",
    "currency_code", "enrollment_date", "effective_from_date",
    "effective_to_date", "current_flag", "record_source", "load_timestamp",
]

# ------------------------------------------------------------
# Vocabularies — small curated lists keep generation deterministic and
# dependency-free (no external name corpus). All synthetic.
# ------------------------------------------------------------
FIRST_NAMES = [
    "James", "Mary", "John", "Patricia", "Robert", "Jennifer", "Michael",
    "Linda", "David", "Elizabeth", "Maria", "Sofia", "Yuki", "Hiroshi",
    "Liam", "Olivia", "Noah", "Emma", "Lucas", "Mia",
]
LAST_NAMES = [
    "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller",
    "Davis", "Rodriguez", "Martinez", "Tanaka", "Sato", "Nguyen", "Patel",
    "Kim", "Muller", "Rossi", "Dubois", "Silva", "Andersson",
]
CITIES = [
    "Springfield", "Riverton", "Fairview", "Lakeside", "Madison",
    "Greenville", "Kingston", "Ashford", "Bridgeport", "Clayton",
]
STATES = ["CA", "NY", "TX", "IL", "WA", "ON", "BC", "QC", "ENG", "NRW"]
COUNTRY_CODES = ["US", "CA", "GB", "FR", "DE", "ES", "IT", "NL", "AU", "JP"]
LANG_CODES = ["en", "fr", "de", "es", "it", "nl", "ja"]
CALLING_CODES = ["1", "44", "33", "49", "34", "39", "31", "61", "81"]

NAME_PREFIXES = ["mr", "mrs", "ms", "mx", "dr"]
NAME_SUFFIXES = ["jr", "sr", "ii", "iii"]
GENDERS = ["female", "male", "non_binary", "prefer_not_to_say"]
CUSTOMER_STATUS = ["prospect", "active", "inactive", "closed"]

ADDRESS_TYPES = ["billing", "shipping", "home", "work", "other"]
CONTACT_TYPES = ["email", "mobile_phone", "landline_phone", "fax"]
CONTACT_STATUS = ["active", "inactive", "bounced", "opted_out"]
CONSENT_TYPES = [
    "marketing_email", "marketing_sms", "marketing_phone", "marketing_postal",
    "data_processing", "third_party_sharing", "profiling", "cookies",
]
CONSENT_STATUS = ["granted", "withdrawn", "pending", "expired"]
LEGAL_BASIS = [
    "consent", "contract", "legitimate_interest", "legal_obligation",
    "vital_interest", "public_task",
]
CAPTURE_CHANNELS = ["web", "mobile_app", "store", "call_center", "email"]
ACCOUNT_TYPES = ["business", "government", "education", "nonprofit", "reseller"]
ACCOUNT_STATUS = ["prospect", "active", "inactive", "closed"]
CURRENCIES = ["USD", "EUR", "GBP", "CAD", "JPY"]
INDUSTRY_CODES = ["445110", "448140", "452210", "454110", "722511", "238210"]

def load_seed_config():
    """Read defaults from synthetic-data/seeds.yaml if present."""
    cfg = {"seed": 1001, "profiles": 1000, "accounts": 120,
           "addr_max": 3, "contact_max": 3, "consent_max": 4}
    path = os.path.join(os.path.dirname(__file__), "..", "seeds.yaml")
    try:
        import yaml
        with open(path) as fh:
            data = yaml.safe_load(fh) or {}
        c = (data.get("domains", {}) or {}).get("customer", {}) or {}
        cfg["seed"] = c.get("seed", cfg["seed"])
        vols = c.get("volumes", {}) or {}
        cfg["profiles"] = vols.get("profiles", cfg["profiles"])
        cfg["accounts"] = vols.get("accounts", cfg["accounts"])
        fan = c.get("fanout", {}) or {}
        cfg["addr_max"] = fan.get("addresses_per_profile_max", cfg["addr_max"])
        cfg["contact_max"] = fan.get("contacts_per_profile_max", cfg["contact_max"])
        cfg["consent_max"] = fan.get("consents_per_profile_max", cfg["consent_max"])
    except Exception:
        pass  # seeds.yaml is optional; fall back to defaults
    return cfg


# Shared deterministic helpers (_pick / _frac / _count_1_to_max) and the
# _write inserter are imported from _common above.


# ------------------------------------------------------------
# Generators
# ------------------------------------------------------------
def build_profiles(spark, n, seed):
    spec = (
        dg.DataGenerator(spark, name="profile", rows=n, partitions=8,
                         randomSeedMethod="fixed", randomSeed=seed)
        .withColumn("profile_id", "string",
                    expr="concat('CUST-', lpad(cast(id as string), 8, '0'))")
        .withColumn("name_prefix", "string", values=NAME_PREFIXES, percentNulls=0.2)
        .withColumn("first_name", "string", values=FIRST_NAMES)
        .withColumn("middle_name", "string", values=FIRST_NAMES, percentNulls=0.6)
        .withColumn("last_name", "string", values=LAST_NAMES)
        .withColumn("name_suffix", "string", values=NAME_SUFFIXES, percentNulls=0.9)
        # dates via integer offsets + date_add for engine-version robustness
        .withColumn("_dob_off", "int", minValue=0, maxValue=20819, omit=True)
        .withColumn("date_of_birth", "date",
                    expr="date_add(date'1950-01-01', _dob_off)")
        .withColumn("gender", "string", values=GENDERS, weights=[46, 46, 4, 4])
        .withColumn("preferred_language_code", "string", values=LANG_CODES)
        .withColumn("nationality_country_code", "string", values=COUNTRY_CODES)
        .withColumn("loyalty_id", "string",
                    expr="concat('LOY-', lpad(cast(id as string), 9, '0'))",
                    percentNulls=0.3)
        .withColumn("household_id", "string",
                    expr="concat('HH-', lpad(cast(cast(id/2 as int) as string), 8, '0'))",
                    percentNulls=0.1)
        .withColumn("customer_status", "string", values=CUSTOMER_STATUS,
                    weights=[10, 70, 15, 5])
        .withColumn("_enr_off", "int", minValue=0, maxValue=3073, omit=True)
        .withColumn("enrollment_date", "date",
                    expr="date_add(date'2018-01-01', _enr_off)")
    )
    df = spec.build()
    # SCD2 + audit: all current (effective from enrollment, open-ended).
    return (df
            .withColumn("effective_from_date", F.col("enrollment_date"))
            .withColumn("effective_to_date", F.lit(None).cast("date"))
            .withColumn("current_flag", F.lit(True))
            .withColumn("record_source", F.lit(RECORD_SOURCE))
            .withColumn("load_timestamp", F.current_timestamp()))


def build_addresses(spark, profiles_current, seed, max_per):
    base = (profiles_current
            .withColumn("_n", _count_1_to_max(max_per, seed, "addr_n", "profile_id"))
            .withColumn("k", F.explode(F.expr("sequence(1, _n)"))))
    return (base
            .withColumn("address_id", F.concat(F.lit("ADDR-"), F.col("profile_id"),
                                               F.lit("-"), F.col("k")))
            .withColumn("address_type",
                        F.when(F.col("k") == 1, F.lit("billing"))
                         .otherwise(_pick(ADDRESS_TYPES, seed, "atype", "profile_id", "k")))
            .withColumn("address_line_1",
                        F.concat((F.abs(F.hash("profile_id", "k", F.lit(seed))) % 9899 + 100).cast("string"),
                                 F.lit(" "), _pick(LAST_NAMES, seed, "street", "profile_id", "k"),
                                 F.lit(" St")))
            .withColumn("address_line_2",
                        F.when(_frac(seed, "line2", "profile_id", "k") < 0.3,
                               F.concat(F.lit("Unit "), (F.abs(F.hash("profile_id", "k", F.lit(seed))) % 50 + 1).cast("string")))
                         .otherwise(F.lit(None).cast("string")))
            .withColumn("city", _pick(CITIES, seed, "city", "profile_id", "k"))
            .withColumn("state_province", _pick(STATES, seed, "state", "profile_id", "k"))
            .withColumn("postal_code",
                        F.lpad((F.abs(F.hash("profile_id", "k", F.lit(seed))) % 100000).cast("string"), 5, "0"))
            .withColumn("country_code", _pick(COUNTRY_CODES, seed, "ctry", "profile_id", "k"))
            .withColumn("latitude",
                        F.round((_frac(seed, "lat", "profile_id", "k") * F.lit(180) - F.lit(90)).cast("decimal(9,6)"), 6))
            .withColumn("longitude",
                        F.round((_frac(seed, "lon", "profile_id", "k") * F.lit(360) - F.lit(180)).cast("decimal(9,6)"), 6))
            .withColumn("is_primary", F.col("k") == 1)
            .withColumn("address_status",
                        F.when(_frac(seed, "astat", "profile_id", "k") < 0.9, F.lit("active"))
                         .otherwise(F.lit("inactive")))
            .withColumn("effective_from_date", F.expr("date_add(date'2018-01-01', cast(abs(hash(profile_id, k)) % 3000 as int))"))
            .withColumn("effective_to_date", F.lit(None).cast("date"))
            .withColumn("current_flag", F.lit(True))
            .withColumn("record_source", F.lit(RECORD_SOURCE))
            .withColumn("load_timestamp", F.current_timestamp()))


def build_contacts(spark, profiles_current, seed, max_per):
    base = (profiles_current
            .withColumn("_n", _count_1_to_max(max_per, seed, "cont_n", "profile_id"))
            .withColumn("k", F.explode(F.expr("sequence(1, _n)"))))
    contact_type = F.when(F.col("k") == 1, F.lit("email")) \
                    .otherwise(_pick(CONTACT_TYPES, seed, "ctype", "profile_id", "k"))
    email_val = F.concat(F.lower(F.col("first_name")), F.lit("."), F.lower(F.col("last_name")),
                         F.lit("."), F.col("profile_id"), F.lit("@example.com"))
    phone_val = F.concat(F.lit("+"), _pick(CALLING_CODES, seed, "cc", "profile_id", "k"),
                         F.lit(" "),
                         F.lpad((F.abs(F.hash("profile_id", "k", F.lit(seed))) % 1000000000).cast("string"), 9, "0"))
    return (base
            .withColumn("contact_type", contact_type)
            .withColumn("contact_id", F.concat(F.lit("CTC-"), F.col("profile_id"), F.lit("-"), F.col("k")))
            .withColumn("contact_value",
                        F.when(F.col("contact_type") == "email", email_val).otherwise(phone_val))
            .withColumn("country_calling_code",
                        F.when(F.col("contact_type") == "email", F.lit(None).cast("string"))
                         .otherwise(_pick(CALLING_CODES, seed, "cc2", "profile_id", "k")))
            .withColumn("is_primary", F.col("k") == 1)
            .withColumn("is_verified", _frac(seed, "verif", "profile_id", "k") < 0.7)
            .withColumn("verified_timestamp",
                        F.when(F.col("is_verified"), F.current_timestamp()).otherwise(F.lit(None).cast("timestamp")))
            .withColumn("contact_status", _pick(CONTACT_STATUS, seed, "cstat", "profile_id", "k"))
            .withColumn("record_source", F.lit(RECORD_SOURCE))
            .withColumn("load_timestamp", F.current_timestamp())
            .withColumn("updated_timestamp", F.current_timestamp()))


def build_consents(spark, profiles_current, seed, max_per):
    # One consent row per distinct consent_type (capped at max_per), so a
    # profile never has two current rows for the same consent_type.
    base = (profiles_current
            .withColumn("_n", _count_1_to_max(max_per, seed, "cons_n", "profile_id"))
            .withColumn("k", F.explode(F.expr("sequence(1, _n)"))))
    # Index consent_type by k so a profile never gets two rows of the same type.
    consent_type = F.element_at(
        F.array(*[F.lit(v) for v in CONSENT_TYPES]),
        ((F.col("k") - 1) % F.lit(len(CONSENT_TYPES))).cast("int") + F.lit(1))
    return (base
            .withColumn("consent_type", consent_type)
            .withColumn("consent_id", F.concat(F.lit("CNS-"), F.col("profile_id"), F.lit("-"), F.col("k")))
            .withColumn("consent_status",
                        F.when(_frac(seed, "cnstat", "profile_id", "k") < 0.75, F.lit("granted"))
                         .otherwise(_pick(CONSENT_STATUS, seed, "cnstat2", "profile_id", "k")))
            .withColumn("legal_basis", _pick(LEGAL_BASIS, seed, "lb", "profile_id", "k"))
            .withColumn("capture_channel", _pick(CAPTURE_CHANNELS, seed, "cap", "profile_id", "k"))
            .withColumn("disclosure_version",
                        F.when(_frac(seed, "disc", "profile_id", "k") < 0.5, F.lit("v1")).otherwise(F.lit("v2")))
            .withColumn("valid_from_timestamp",
                        F.expr("cast(date_add(date'2019-01-01', cast(abs(hash(profile_id, k)) % 2500 as int)) as timestamp)"))
            .withColumn("valid_to_timestamp", F.lit(None).cast("timestamp"))
            .withColumn("current_flag", F.lit(True))
            .withColumn("record_source", F.lit(RECORD_SOURCE))
            .withColumn("load_timestamp", F.current_timestamp()))


def build_accounts(spark, profiles_current, n, seed):
    num_profiles = profiles_current.count()
    spec = (
        dg.DataGenerator(spark, name="account", rows=n, partitions=4,
                         randomSeedMethod="fixed", randomSeed=seed)
        .withColumn("account_id", "string",
                    expr="concat('ACCT-', lpad(cast(id as string), 6, '0'))")
        .withColumn("account_name", "string",
                    expr="concat('Synthetic Org ', lpad(cast(id as string), 6, '0'))")
        .withColumn("account_type", "string", values=ACCOUNT_TYPES,
                    weights=[60, 5, 10, 10, 15])
        .withColumn("registration_number", "string",
                    expr="concat('REG', lpad(cast(id as string), 9, '0'))")
        .withColumn("tax_id", "string",
                    expr="concat('TAX', lpad(cast(id as string), 9, '0'))")
        .withColumn("gln", "string",
                    expr="lpad(cast((id * 7 + 1000000000000) as string), 13, '0')")
        .withColumn("industry_classification_code", "string", values=INDUSTRY_CODES)
        .withColumn("account_status", "string", values=ACCOUNT_STATUS,
                    weights=[10, 70, 15, 5])
        .withColumn("_credit", "int", minValue=5, maxValue=500, omit=True)
        .withColumn("credit_limit_amount", "decimal(18,2)",
                    expr="cast(_credit * 1000 as decimal(18,2))")
        .withColumn("currency_code", "string", values=CURRENCIES)
        .withColumn("_enr_off", "int", minValue=0, maxValue=3073, omit=True)
        .withColumn("enrollment_date", "date",
                    expr="date_add(date'2018-01-01', _enr_off)")
        # row index used to map a primary contact + optional parent
        .withColumn("_idx", "long", expr="id", omit=True)
    )
    acc = spec.build()

    # Map a primary-contact profile deterministically by row index.
    indexed_profiles = (profiles_current
                        .withColumn("_pidx", F.row_number().over(Window.orderBy("profile_id")) - 1)
                        .select(F.col("profile_id").alias("_pc_profile_id"), "_pidx"))
    acc = (acc
           .withColumn("_pidx", (F.col("_idx") % F.lit(max(1, num_profiles))))
           .join(indexed_profiles, on="_pidx", how="left")
           .withColumnRenamed("_pc_profile_id", "primary_contact_profile_id"))

    return (acc
            .withColumn("parent_account_id",
                        F.when((_frac(seed, "parent", "account_id") < 0.2) & (F.col("_idx") > 0),
                               F.concat(F.lit("ACCT-"),
                                        F.lpad(((F.col("_idx") - 1)).cast("string"), 6, "0")))
                         .otherwise(F.lit(None).cast("string")))
            .withColumn("effective_from_date", F.col("enrollment_date"))
            .withColumn("effective_to_date", F.lit(None).cast("date"))
            .withColumn("current_flag", F.lit(True))
            .withColumn("record_source", F.lit(RECORD_SOURCE))
            .withColumn("load_timestamp", F.current_timestamp()))


# ------------------------------------------------------------
# Orchestration
# ------------------------------------------------------------
def generate(spark, catalog, customer_schema, num_profiles, num_accounts, seed, mode,
             addr_max=3, contact_max=3, consent_max=4):
    if not catalog:
        raise ValueError("`catalog` parameter is required (guardrail #1: no hardcoded catalog).")

    def fq(table):
        return f"{catalog}.{customer_schema}.{table}"

    print(f"[ordm] generating customer domain into {catalog}.{customer_schema} "
          f"(profiles={num_profiles}, accounts={num_accounts}, seed={seed}, mode={mode})")

    # 1. profiles -> write -> read back surrogate keys
    profiles = build_profiles(spark, num_profiles, seed)
    _write(spark, profiles, fq("profile"), PROFILE_COLUMNS, mode)
    profiles_current = (spark.table(fq("profile"))
                        .where("current_flag = true")
                        .select("profile_id", "profile_sk", "first_name", "last_name"))

    # 2. children (carry real profile_sk for the declared FK)
    addresses = build_addresses(spark, profiles_current.select("profile_id", "profile_sk"),
                                seed, addr_max)
    _write(spark, addresses, fq("address"), ADDRESS_COLUMNS, mode)

    contacts = build_contacts(spark, profiles_current, seed, contact_max)
    _write(spark, contacts, fq("contact"), CONTACT_COLUMNS, mode)

    consents = build_consents(spark, profiles_current.select("profile_id", "profile_sk"),
                              seed, consent_max)
    _write(spark, consents, fq("consent"), CONSENT_COLUMNS, mode)

    # 3. accounts (B2B) referencing profiles by business key
    accounts = build_accounts(spark, profiles_current.select("profile_id"), num_accounts, seed)
    _write(spark, accounts, fq("account"), ACCOUNT_COLUMNS, mode)

    print("[ordm] customer domain generation complete.")


def main():
    spark = SparkSession.builder.getOrCreate()
    cfg = load_seed_config()
    catalog = get_param("catalog", "")
    customer_schema = get_param("customer_schema", "customer")
    num_profiles = int(get_param("num_profiles", cfg["profiles"]))
    num_accounts = int(get_param("num_accounts", cfg["accounts"]))
    seed = int(get_param("seed", cfg["seed"]))
    mode = get_param("mode", "overwrite")
    generate(spark, catalog, customer_schema, num_profiles, num_accounts, seed, mode,
             addr_max=int(cfg["addr_max"]), contact_max=int(cfg["contact_max"]),
             consent_max=int(cfg["consent_max"]))


if __name__ == "__main__":
    main()
