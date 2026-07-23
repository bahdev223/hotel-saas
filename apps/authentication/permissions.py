from .groups import PROMOTEUR, RAF


def est_lecture_seule(user):
    return user.is_authenticated and user.groups.filter(name=PROMOTEUR).exists()


def est_raf(user):
    return user.is_authenticated and user.groups.filter(name=RAF).exists()
