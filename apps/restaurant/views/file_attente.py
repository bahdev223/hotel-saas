from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.utils import timezone

from ..models import FileAttenteModel
from ..models import TableModel


def get_tables_libres():
    """Retourne les tables non assignées"""
    return TableModel.objects.filter(
        actif=True, statut='LIBRE'
    ).order_by('numero')


@login_required
def file_attente(request):
    """File d'attente des clients"""
    files = FileAttenteModel.objects.filter(statut='EN_ATTENTE').order_by('-date_entree')
    tables_libres = get_tables_libres()

    if request.method == 'POST':
        try:
            if 'ajouter' in request.POST:
                FileAttenteModel.objects.create(
                    nombre_personnes=int(request.POST.get('nombre_personnes', 1)),
                    nom_client=request.POST.get('nom_client', ''),
                    telephone=request.POST.get('telephone', ''),
                    statut='EN_ATTENTE'
                )
                messages.success(request, 'Client ajouté à la file d\'attente')

            elif 'placer' in request.POST:
                file_id = request.POST.get('file_id')
                table_numero = request.POST.get('table_numero')
                entry = FileAttenteModel.objects.filter(id=file_id, statut='EN_ATTENTE').first()
                if entry:
                    table = TableModel.objects.filter(numero=table_numero, actif=True).first()
                    if table:
                        entry.table_assigned = table_numero
                        entry.statut = 'PLACE'
                        entry.save()
                        table.statut = 'OCCUPEE'
                        table.save()
                        messages.success(request, 'Client placé à une table')
                    else:
                        messages.error(request, 'Table introuvable')
                else:
                    messages.error(request, 'Entrée file d\'attente introuvable')

            return redirect('restaurant:file_attente')
        except Exception as e:
            messages.error(request, str(e))

    context = {
        'files': files,
        'tables_libres': tables_libres,
    }
    return render(request, 'restaurant/file_attente.html', context)

