from apps.authentication.permissions import est_lecture_seule, est_raf
from apps.authentication.groups import PROMOTEUR, RAF


def promoteur_context(request):
    user = request.user
    est_prom = est_lecture_seule(user)
    est_raf_user = est_raf(user)
    est_superuser = user.is_authenticated and user.is_superuser
    return {
        'est_promoteur': est_prom,
        'est_raf': est_raf_user,
        'est_superuser': est_superuser,
        'est_admin': est_raf_user or est_superuser,
        'a_planning': est_raf_user or est_superuser,
        'est_bloque_stock': est_prom,
        'est_bloque_restaurant': est_prom,
        'est_bloque_hotel': est_prom,
        'est_bloque_compta': est_prom,
        'est_bloque_tresorerie': est_prom,
        'est_bloque_brasserie': est_prom,
    }
