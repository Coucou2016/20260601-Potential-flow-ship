import numpy as np
from scripts.audit_conservative_fullband_candidate import paired_responses


def test_exact_complex_increment_decomposition():
    m=np.diag([2.,3.])
    c=np.array([[40.,3.],[4.,50.]])
    old=np.array([[2-3j,1+.2j],[.4j,3-2j]])
    new=old+np.array([[1+.5j,.3j],[.7,2.]])
    f=np.array([1+2j,3-.2j])
    r=paired_responses(m,c,old,new,f,f+np.array([.3j,.5]),2.)
    np.testing.assert_allclose(r['combined']-r['baseline'],
        r['radiation_increment']+r['excitation_increment'],rtol=1e-13,atol=1e-15)


def test_unchanged_operators_produce_identical_responses():
    m=np.eye(2); c=10*np.eye(2); rad=np.eye(2)*(1-2j); f=np.array([1j,2])
    r=paired_responses(m,c,rad,rad,f,f,1.)
    for name in ('radiation_only','excitation_only','combined'):
        np.testing.assert_allclose(r[name],r['baseline'])
    np.testing.assert_allclose(r['radiation_increment'],0)
    np.testing.assert_allclose(r['excitation_increment'],0)
