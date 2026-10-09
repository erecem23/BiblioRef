from copy import deepcopy
import app


def _doc(analysis, refs=True, corrections=None):
    return {
        'status': 'ready',
        'analysis': analysis,
        'references': [{'id':'r1','text':'Altieri','deleted':False}] if refs else [],
        'sections': [{'id':'s1','start_page':24,'end_page':28}] if refs else [],
        'corrections': corrections or [],
    }


def test_v095_persisted_analysis_is_stale_under_v096():
    d=_doc({'software_version':'0.9.5','algorithm_version':'0.6.1','stable_engine_version':'0.4.4'})
    assert app._analysis_stale(d) is True
    pub=app._public_doc(d, True)
    assert pub['analysis_stale'] is True
    assert pub['current_versions']['software_version']=='0.9.10-rc2'


def test_v096_current_analysis_is_not_stale():
    d=_doc({'software_version':app.SOFTWARE_VERSION,'algorithm_version':app.ALGORITHM_VERSION,'stable_engine_version':app.STABLE_ENGINE_VERSION,'extraction_revision':app.EXTRACTION_REVISION})
    assert app._analysis_stale(d) is False


def test_missing_version_provenance_is_stale():
    assert app._analysis_stale(_doc({})) is True


def test_unprocessed_document_is_not_called_stale():
    d=_doc({}, refs=False)
    d['status']='uploaded'
    assert app._analysis_stale(d) is False


def test_snapshot_preserves_old_refs_and_corrections():
    d=_doc({'software_version':'0.9.5','algorithm_version':'0.6.1','stable_engine_version':'0.4.4'}, corrections=[{'kind':'edit'}])
    old=deepcopy(d['references'])
    app._archive_analysis_snapshot(d,'test')
    assert len(d['analysis_history'])==1
    snap=d['analysis_history'][0]
    assert snap['versions']['software_version']=='0.9.5'
    assert snap['references']==old
    assert snap['corrections']==[{'kind':'edit'}]
