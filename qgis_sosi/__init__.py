def classFactory(iface):
    from .plugin import SurveyFilePlugin

    return SurveyFilePlugin(iface)
