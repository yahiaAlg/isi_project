"""
Context processors for core app.
"""
from .models import InstituteInfo, BureauEtudeInfo, FormationInfo


def institute_info(request):
    """
    Add institute information to template context.
    """
    try:
        institute = InstituteInfo.get_instance()
    except:
        institute = None
    
    try:
        bureau_etude = BureauEtudeInfo.get_instance()
    except:
        bureau_etude = None
    
    try:
        formation_info = FormationInfo.get_instance()
    except:
        formation_info = None
    
    return {
        'INSTITUTE': institute,
        'BUREAU_ETUDE': bureau_etude,
        'FORMATION_INFO': formation_info,
    }
