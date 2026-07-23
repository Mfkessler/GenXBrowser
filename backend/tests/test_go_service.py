from h5ad_lib.search.go_service import GOService


def make_service():
    service = GOService.__new__(GOService)
    service.loaded = True
    service.go_index = {
        "GO:0009908": {
            "id": "GO:0009908",
            "name": "flower development",
            "namespace": "biological_process",
            "definition": "The process whose specific outcome is the progression of a flower.",
        },
        "GO:0006950": {
            "id": "GO:0006950",
            "name": "response to stress",
            "namespace": "biological_process",
            "definition": "A change in state resulting from stress.",
        },
        "GO:1234567": {
            "id": "GO:1234567",
            "name": "unrelated process",
            "namespace": "biological_process",
            "definition": "A flower-specific cellular response.",
        },
    }
    service.name_index = {
        "flower": ["GO:0009908"],
        "development": ["GO:0009908"],
        "response": ["GO:0006950"],
        "stress": ["GO:0006950"],
        "unrelated": ["GO:1234567"],
        "process": ["GO:1234567"],
    }
    service.definition_index = {
        "flower": ["GO:0009908", "GO:1234567"],
        "specific": ["GO:0009908", "GO:1234567"],
        "stress": ["GO:0006950"],
    }
    return service


def test_search_terms_matches_definitions_and_respects_dataset_candidates():
    service = make_service()

    results = service.search_terms(
        "flower",
        limit=20,
        candidate_ids={"GO:1234567"},
    )

    assert [result["id"] for result in results] == ["GO:1234567"]