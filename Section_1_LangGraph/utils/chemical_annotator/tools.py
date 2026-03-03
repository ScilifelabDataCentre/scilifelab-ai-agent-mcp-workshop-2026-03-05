"""
=== Chemical Annotator - Notebook Version ===
Fetches drug annotations from public repositories based on exact match with query pattern.
"""
VERSION = "1.0"
AUTHOR = "Flavio Ballante"
INSTITUTION = "2025, CBCS-SciLifeLab-Karolinska Institutet"
CONTACT = "flavio.ballante@ki.se, flavioballante@gmail.com"

import logging
import re
from pathlib import Path

import pandas as pd
from utils.chemical_annotator.misc_utils import find_smiles_column, process_compounds, resolve_smiles_any
from utils.chemical_annotator.chembl_utils import process_targets, get_protein_classifications, trace_hierarchy, chembl_status
from utils.chemical_annotator.kegg_utils import get_pathways_from_ec
from langchain_core.tools import tool


def _looks_like_smiles(value: str) -> bool:
    if not value or " " in value:
        return False
    return bool(re.search(r"[0-9=#@\[\]()/\\]", value))


def _infer_identifier_kind(value: str) -> str | None:
    if re.fullmatch(r"CHEMBL\d+", value.strip(), flags=re.IGNORECASE):
        return "chembl"
    if re.fullmatch(r"[A-Z]{14}-[A-Z]{10}-[A-Z]", value.strip()):
        return "inchikey"
    if value.strip().startswith("InChI="):
        return "inchi"
    if _looks_like_smiles(value):
        return "smiles"
    return "name"



@tool
def annotate_chemicals(
    compounds: list[str] | str,
    confidence_threshold: int = 8,
    assay_type_in: str = "B,F",
    pchembl_value_gte: float = 6.0,
    log_file: str = "chemical_annotator.log",
):
    """
    Demo-friendly chemical annotator.
    Takes a list of compound identifiers (any type), resolves them to SMILES,
    then runs the standard annotation pipeline.
    
    Parameters
    ----------
    compounds : list or str
        Compound identifier(s) (names, ChEMBL IDs, InChIKey, InChI, or SMILES).
    confidence_threshold : int, optional
        Minimum confidence score value (default: 8)
    assay_type_in : str, optional
        Comma-separated list of assay types (default: 'B,F')
    pchembl_value_gte : float, optional
        Minimum pChEMBL value (default: 6.0)
    log_file : str, optional
        Path to log file (default: 'chemical_annotator.log')
    
    Returns
    -------
    dict
        Dictionary with resolved input plus annotation tables serialized as lists of records.
    """

    # Store artifacts under the active conversation's results directory.
    output_dir = Path("outputs")
    safe_prefix = "annotations"
    log_path = output_dir / f"{safe_prefix}_{Path(str(log_file)).name}"

    # Remove previous log file if it exists
    if log_path.exists():
        log_path.unlink()
    
    # Configure logging
    logging.basicConfig(
        filename=str(log_path),
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger()
    
    try:
        # Add title/header to the log file
        logger.info("===========================================")
        logger.info("            Chemical Annotator             ")
        logger.info(f"Version:  {VERSION}")
        logger.info("Format: txt")
        logger.info(f"Author: {AUTHOR}")
        logger.info(f"Contact: {CONTACT}")
        logger.info(f"Institution: {INSTITUTION}")
        logger.info("===========================================")
        
        if chembl_status:
            logger.info(f"ChEMBL Database Version: {chembl_status['chembl_db_version']}")
            logger.info(f"ChEMBL Release Date: {chembl_status['chembl_release_date']}")
            logger.info(f"ChEMBL Status: {chembl_status['status']}")
            logger.info(f"Number of Activities: {chembl_status['activities']}")
            logger.info(f"Number of Distinct Compounds: {chembl_status['disinct_compounds']}")
            logger.info(f"Number of Targets: {chembl_status['targets']}")
        else:
            logger.warning("Unable to fetch ChEMBL status information")
        
        logger.info("===========================================")
        logger.info("")

        if compounds is None:
            compounds = []
        if isinstance(compounds, str):
            compounds = [compounds]
        if not isinstance(compounds, list):
            raise ValueError("compounds must be a list of identifiers or a single string.")
        if not compounds:
            raise ValueError(
                "No compounds provided. Please pass a list like ['aspirin', 'CHEMBL25']."
            )

        resolved_rows = []
        for raw in compounds:
            if raw is None:
                continue
            ident_value = str(raw).strip()
            if not ident_value:
                continue
            ident_kind = _infer_identifier_kind(ident_value)
            smiles = None
            if ident_kind == "smiles":
                smiles = ident_value
            else:
                smiles = resolve_smiles_any(
                    ident_value,
                    identifier_type=ident_kind if ident_kind in {"chembl", "inchikey", "inchi"} else None,
                )
                if not smiles and _looks_like_smiles(ident_value):
                    smiles = ident_value
            resolved_rows.append(
                {
                    "identifier": ident_value,
                    "identifier_type": ident_kind,
                    "SMILES": smiles,
                }
            )

        resolved_df = pd.DataFrame(resolved_rows)
        if resolved_df.empty:
            raise ValueError("No valid compound identifiers found in the list.")
        compounds_list = resolved_df.dropna(subset=["SMILES"]).reset_index(drop=True)
        if compounds_list.empty:
            raise ValueError(
                "Unable to resolve any identifiers to SMILES. "
                "Please provide valid drug names, ChEMBL IDs, or SMILES."
            )
        else:
            unresolved = resolved_df[resolved_df["SMILES"].isna()]
            if not unresolved.empty:
                logger.warning(
                    "Some identifiers could not be resolved to SMILES: %s",
                    ", ".join(unresolved["identifier"].astype(str).tolist()),
                )

        # Always resolve to SMILES before querying downstream sources.
        smiles_column = find_smiles_column(compounds_list)
        if smiles_column and smiles_column != "SMILES":
            compounds_list["SMILES"] = compounds_list[smiles_column]

        # Fetch data from ChEMBL
        print("Processing compounds...")
        Drugs_data = process_compounds(
            compounds_list,
            "SMILES",
            confidence_threshold=confidence_threshold,
            assay_type_in=assay_type_in.split(','),
            pchembl_value_gte=pchembl_value_gte
        )

        # Shift index by 1
        Drugs_info = Drugs_data[0]
        Drugs_assay = Drugs_data[1]
        Drugs_MoA = Drugs_data[2]
        compound_status = Drugs_data[3] if len(Drugs_data) > 3 else pd.DataFrame()
        Drugs_info.index = Drugs_info.index + 1
        Drugs_assay.index = Drugs_assay.index + 1
        Drugs_MoA.index = Drugs_MoA.index + 1
     
        print("All compounds have been processed. Now processing targets data...")
        logger.info("All compounds have been processed. Now processing targets data...")

        # Fetch target data from ChEMBL
        Targets_data = process_targets(Drugs_assay)
        Targets_data = Targets_data.reset_index(drop=True)
        Targets_data.index = Targets_data.index + 1
        if "target_chembl_id" not in Targets_data.columns:
            Targets_data["target_chembl_id"] = pd.Series(dtype=object)
        
        # Process EC numbers and get pathway information
        print("Processing EC numbers and retrieving pathway information...")
        logger.info("Processing EC numbers and retrieving pathway information...")

        pathway_data = []
        if "EC Numbers" in Targets_data.columns:
            unique_targets = Targets_data.drop_duplicates(subset=['target_chembl_id'])
            unique_targets = unique_targets.dropna(subset=['EC Numbers'])
            for _, row in unique_targets.iterrows():
                chembl_id = row['target_chembl_id']
                ec_list = row['EC Numbers']

                if pd.isna(ec_list):
                    continue

                ec_numbers = ec_list.split(';')
                kegg_ids = []
                pathways = []

                for ec in ec_numbers:
                    ec = ec.strip()
                    ec_pathways = get_pathways_from_ec(ec)
        
                    if not ec_pathways.empty:
                        kegg_ids.extend(ec_pathways['KEGG_ID'].unique())
                        pathways.extend(ec_pathways['Pathway'].unique())

                kegg_ids = list(dict.fromkeys(kegg_ids))
                pathways = list(dict.fromkeys(pathways))
        
                pathway_data.append({
                    'target_chembl_id': chembl_id,
                    'EC Numbers': ec_list,
                    'KEGG_ID': ';'.join(kegg_ids),
                    'Pathway': ';'.join(pathways)
                })

        if pathway_data:
            pathway_data = pd.DataFrame(pathway_data)
        else:
            pathway_data = pd.DataFrame(
                columns=["target_chembl_id", "EC Numbers", "KEGG_ID", "Pathway"]
            )

        # Merge pathway_data with Targets_data
        Targets_data = Targets_data.drop(columns=['EC Numbers'], errors='ignore')
        Targets_data_with_pathways = pd.merge(
            Targets_data, pathway_data, on="target_chembl_id", how="left"
        )
        
        # Process protein hierarchy data
        print("Retrieving protein hierarchy information...")
        logger.info("Retrieving protein hierarchy information...")
        
        unique_targets = Targets_data.drop_duplicates(subset=['target_chembl_id']).copy()
        unique_targets['protein_classifications'] = unique_targets['target_chembl_id'].apply(get_protein_classifications)
        unique_targets['protein_hierarchy'] = unique_targets['protein_classifications'].apply(trace_hierarchy)
        
        Targets_data_with_pathways_p_class = Targets_data_with_pathways.merge(
            unique_targets[['target_chembl_id', 'protein_classifications', 'protein_hierarchy']],
            on='target_chembl_id',
            how='left'
        )

        Targets_data_with_pathways_p_class = Targets_data_with_pathways_p_class.reset_index(drop=True)
        Targets_data_with_pathways_p_class.index += 1

        # Concatenate dataframes horizontally
        Drugs_assay_Targets_data = pd.concat(
            [Drugs_assay, Targets_data_with_pathways_p_class.drop('target_chembl_id', axis=1)],
            axis=1
        )

        # Reorder columns (if target_chembl_id is available)
        targets_columns = [col for col in Targets_data_with_pathways_p_class.columns if col != 'target_chembl_id']
        if 'target_chembl_id' in Drugs_assay_Targets_data.columns:
            insert_position = Drugs_assay_Targets_data.columns.get_loc('target_chembl_id') + 1

            new_column_order = (
                list(Drugs_assay_Targets_data.columns[:insert_position]) +
                targets_columns +
                [col for col in Drugs_assay_Targets_data.columns[insert_position:] if col not in targets_columns]
            )

            Drugs_assay_Targets_data = Drugs_assay_Targets_data[new_column_order]
        else:
            logger.warning(
                "target_chembl_id column missing from assay data; skipping column reordering."
            )
        Drugs_assay_Targets_data = Drugs_assay_Targets_data.reset_index(drop=True)
        Drugs_assay_Targets_data.index = Drugs_assay_Targets_data.index + 1
        
        def _df_records(df: pd.DataFrame) -> list[dict]:
            if df is None or df.empty:
                return []
            return df.to_dict(orient="records")

        output_files = {
            "Output description": "Below are annotation tables serialized as record dictionaries.",
            "Data": {
                "drugs_info": _df_records(Drugs_info),
                "drugs_assay": _df_records(Drugs_assay),
                "drugs_moa": _df_records(Drugs_MoA),
                "compound_status": _df_records(compound_status),
                "targets_info": _df_records(Targets_data),
                "pathway_info": _df_records(pathway_data),
                "drugs_assay_targets_info": _df_records(Drugs_assay_Targets_data),
                "resolved_input": _df_records(resolved_df),
                "log_file": str(log_path),
            },
        }
        
        print("Script execution completed successfully.")
        logger.info("Script execution completed successfully.")
        
        # Return only a lightweight description map for agent context
        return output_files
        
    except Exception as e:
        logger.exception("An error occurred: %s", str(e))
        raise
