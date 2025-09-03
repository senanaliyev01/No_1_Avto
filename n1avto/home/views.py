from django.shortcuts import render
from django.http import JsonResponse
from .models import Mehsul, Firma, Reklam
import os
import json
import uuid
import math
from django.conf import settings
from django.views.decorators.http import require_POST
from django.contrib.admin.views.decorators import staff_member_required
import re
from functools import reduce
from operator import and_, or_
from django.db.models import Q, Value, CharField
from django.db.models.functions import Concat
import re

try:
    import pandas as pd
except Exception:  # pragma: no cover
    pd = None


def home(request):
    query = request.GET.get('q', '')
    
    if query:
        mehsullar = get_search_filtered_products(Mehsul.objects.all(), query)
    else:
        mehsullar = Mehsul.objects.all()

    # AJAX sorğusu olarsa JSON qaytar
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        data = []
        for m in mehsullar:
            data.append({
                'adi': m.adi,
                'firma': m.firma.adi,
                'kod': m.kod,
                'qiymet': str(m.qiymet),
                'stok': m.stok,
                'sekil': m.sekil.url if m.sekil else ''
            })
        return JsonResponse({'results': data})

    # Reklamları əldə et
    reklamlar = Reklam.objects.all()
    
    return render(request, 'base.html', {
        'mehsullar': mehsullar, 
        'query': query,
        'reklamlar': reklamlar
    })


# Legacy path (not used by JS). Kept for completeness.
@staff_member_required
@require_POST
def import_user_products_view(request):
    return JsonResponse({'status': 'error', 'message': 'Bu endpoint istifadə olunmur. Zəhmət olmasa /my-products/import/init|batch|finalize istifadə edin.'}, status=405)


@staff_member_required
@require_POST
def import_user_products_init(request):
    if pd is None:
        return JsonResponse({'status': 'error', 'message': 'Pandas quraşdırılmayıb.'}, status=500)

    excel_file = request.FILES.get('excel_file')
    if not excel_file:
        return JsonResponse({'status': 'error', 'message': 'Excel faylı seçin.'}, status=400)
    if not excel_file.name.endswith('.xlsx'):
        return JsonResponse({'status': 'error', 'message': 'Yalnız .xlsx faylı qəbul edilir.'}, status=400)

    imports_dir = os.path.join(settings.MEDIA_ROOT, 'imports')
    os.makedirs(imports_dir, exist_ok=True)
    job_id = str(uuid.uuid4())
    saved_path = os.path.join(imports_dir, f'job_{job_id}.xlsx')
    with open(saved_path, 'wb+') as dest:
        for chunk in excel_file.chunks():
            dest.write(chunk)

    try:
        df = pd.read_excel(saved_path)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': f'Excel oxunmadı: {e}'}, status=400)

    cleaned_rows = []
    columns_display = [str(c) for c in df.columns]
    for _index, row in df.iterrows():
        row_dict = {str(k).strip().lower(): v for k, v in row.items()}
        cleaned_rows.append(row_dict)

    total_rows = len(cleaned_rows)

    jobs_dir = os.path.join(imports_dir, 'jobs')
    os.makedirs(jobs_dir, exist_ok=True)
    job_state_path = os.path.join(jobs_dir, f'{job_id}.json')
    job_state = {
        'total_rows': total_rows,
        'processed_rows': 0,
        'new_count': 0,
        'update_count': 0,
        'error_count': 0,
        'deleted_count': 0,
        'excel_product_keys': [],  # (kod, firma_id)
        'error_details': [],
        'rows': cleaned_rows,
        'columns_display': columns_display,
    }
    with open(job_state_path, 'w', encoding='utf-8') as f:
        json.dump(job_state, f, ensure_ascii=False)

    return JsonResponse({'status': 'ok', 'job_id': job_id, 'total_rows': total_rows})


@staff_member_required
@require_POST
def import_user_products_batch(request):
    job_id = request.POST.get('job_id')
    try:
        start = int(request.POST.get('start', 0))
        size = int(request.POST.get('size', 100))
    except ValueError:
        return JsonResponse({'status': 'error', 'message': 'start/size yanlışdır.'}, status=400)

    imports_dir = os.path.join(settings.MEDIA_ROOT, 'imports')
    job_state_path = os.path.join(imports_dir, 'jobs', f'{job_id}.json')
    if not os.path.exists(job_state_path):
        return JsonResponse({'status': 'error', 'message': 'Job tapılmadı.'}, status=404)

    with open(job_state_path, 'r', encoding='utf-8') as f:
        state = json.load(f)

    rows = state.get('rows', [])
    subset = rows[start:start + size]
    if not subset:
        return JsonResponse({
            'status': 'ok',
            'message': 'Heç nə yoxdur',
            'processed_rows': state.get('processed_rows', 0),
            'new_count': state.get('new_count', 0),
            'update_count': state.get('update_count', 0),
            'error_count': state.get('error_count', 0),
        })

    new_count = state.get('new_count', 0)
    update_count = state.get('update_count', 0)
    error_count = state.get('error_count', 0)
    excel_keys = set(tuple(k) for k in state.get('excel_product_keys', []))
    error_details = state.get('error_details', [])
    batch_errors = []

    for idx, row in enumerate(subset, start=start):
        try:
            excel_line_no = idx + 2  # başlıq 1-ci sətir
            # Snapshot
            full_row = {str(k): ('' if (k not in row or pd.isna(row.get(k))) else str(row.get(k))) for k in row.keys()} if pd else {str(k): str(row.get(k, '')) for k in row.keys()}
            row_errors = []

            def add_err(field_name, message):
                row_errors.append({
                    'line': excel_line_no,
                    'message': message,
                    'field': field_name,
                    'row': full_row,
                })

            # Required: adi, kod, firma, qiymet, stok
            name_val = row.get('adi') if 'adi' in row else ''
            code_val = row.get('kod') if 'kod' in row else ''
            firma_val = row.get('firma') if 'firma' in row else ''
            qiymet_val = row.get('qiymet') if 'qiymet' in row else ''
            stok_val = row.get('stok') if 'stok' in row else ''

            if (name_val is None) or (str(name_val).strip() == '') or (pd and pd.isna(name_val)):
                add_err('adi', 'Məhsulun adı boşdur')
            if (code_val is None) or (str(code_val).strip() == '') or (pd and pd.isna(code_val)):
                add_err('kod', 'Kod boşdur')
            if (firma_val is None) or (str(firma_val).strip() == '') or (pd and pd.isna(firma_val)):
                add_err('firma', 'Firma boşdur')

            # qiymet parse
            if (qiymet_val is None) or (str(qiymet_val).strip() == '') or (pd and pd.isna(qiymet_val)):
                qiymet_parsed = None
                add_err('qiymet', 'qiymet boşdur')
            else:
                try:
                    qiymet_parsed = float(str(qiymet_val).replace(',', '.'))
                except Exception:
                    qiymet_parsed = None
                    add_err('qiymet', 'qiymet rəqəm olmalıdır')

            # stok parse
            if (stok_val is None) or (str(stok_val).strip() == '') or (pd and pd.isna(stok_val)):
                stok_parsed = None
                add_err('stok', 'stok boşdur')
            else:
                try:
                    stok_parsed = int(float(str(stok_val).replace(',', '.')))
                except Exception:
                    stok_parsed = None
                    add_err('stok', 'stok tam ədəd olmalıdır')

            if row_errors:
                error_count += len(row_errors)
                batch_errors.extend(row_errors)
                continue

            temiz_ad = ' '.join(str(name_val).strip().split())
            temiz_kod = str(code_val).strip()
            firma_name = str(firma_val).strip()
            firma_obj, _ = Firma.objects.get_or_create(adi=firma_name)

            excel_keys.add((temiz_kod, firma_obj.id))

            existing = Mehsul.objects.filter(kod=temiz_kod, firma=firma_obj).first()
            if existing:
                existing.adi = temiz_ad
                existing.qiymet = qiymet_parsed or 0
                existing.stok = stok_parsed or 0
                if 'kodlar' in row and row.get('kodlar') not in (None, '') and not (pd and pd.isna(row.get('kodlar'))):
                    existing.kodlar = str(row.get('kodlar'))
                existing.save()
                update_count += 1
            else:
                Mehsul.objects.create(
                    adi=temiz_ad,
                    kod=temiz_kod,
                    firma=firma_obj,
                    qiymet=qiymet_parsed or 0,
                    stok=stok_parsed or 0,
                    kodlar=(str(row.get('kodlar')) if ('kodlar' in row and row.get('kodlar') not in (None, '') and not (pd and pd.isna(row.get('kodlar')))) else '')
                )
                new_count += 1
        except Exception as e:  # noqa: BLE001
            error_count += 1
            batch_errors.append({
                'line': idx + 2,
                'message': str(e),
                'field': None,
                'row': full_row if 'full_row' in locals() else {},
            })
            continue

    state['new_count'] = new_count
    state['update_count'] = update_count
    state['error_count'] = error_count
    state['processed_rows'] = min(state.get('total_rows', 0), start + len(subset))
    state['excel_product_keys'] = list(excel_keys)
    if batch_errors:
        error_details.extend(batch_errors)
        state['error_details'] = error_details
    with open(job_state_path, 'w', encoding='utf-8') as f:
        json.dump(state, f, ensure_ascii=False)

    return JsonResponse({
        'status': 'ok',
        'processed_rows': state['processed_rows'],
        'total_rows': state.get('total_rows', 0),
        'new_count': new_count,
        'update_count': update_count,
        'error_count': error_count,
        'errors': batch_errors,
        'columns': state.get('columns_display') or [],
    })


@staff_member_required
@require_POST
def import_user_products_finalize(request):
    job_id = request.POST.get('job_id')
    imports_dir = os.path.join(settings.MEDIA_ROOT, 'imports')
    job_state_path = os.path.join(imports_dir, 'jobs', f'{job_id}.json')
    if not os.path.exists(job_state_path):
        return JsonResponse({'status': 'error', 'message': 'Job tapılmadı.'}, status=404)

    with open(job_state_path, 'r', encoding='utf-8') as f:
        state = json.load(f)

    excel_keys = set(tuple(k) for k in state.get('excel_product_keys', []))
    deleted_count = 0
    if excel_keys:
        # Diqqət: bütün məhsullara tətbiq olunur
        to_delete_ids = [
            p.id for p in Mehsul.objects.only('id', 'kod', 'firma_id')
            if (p.kod, p.firma_id) not in excel_keys
        ]
        if to_delete_ids:
            deleted_count, _ = Mehsul.objects.filter(id__in=to_delete_ids).delete()

    # Faylları təmizlə
    try:
        file_path = os.path.join(imports_dir, f'job_{job_id}.xlsx')
        if os.path.exists(file_path):
            os.remove(file_path)
    except Exception:
        pass
    try:
        os.remove(job_state_path)
    except Exception:
        pass

    return JsonResponse({
        'status': 'ok',
        'deleted_count': deleted_count,
        'total_errors': len(state.get('error_details', [])),
        'error_details': state.get('error_details', []),
        'columns': state.get('columns_display') or []
    })


def get_search_filtered_products(queryset, search_query):
    if not search_query:
        return queryset

    queryset = queryset.annotate(
        search_text=Concat(
            'adi', Value(' '),
            'kod', Value(' '),
            'firma__adi', Value(' '),
            'kodlar', Value(' '),
            output_field=CharField()
        )
    )
    processed_query = re.sub(r'\s+', ' ', search_query).strip()
    search_words = processed_query.split()
    clean_search = re.sub(r'[^a-zA-Z0-9]', '', search_query.lower())

    def normalize_azerbaijani_chars(text):
        char_map = {
            'ə': 'e', 'e': 'ə', 'Ə': 'E', 'E': 'Ə',
            'ö': 'o', 'o': 'ö', 'Ö': 'O', 'O': 'Ö',
            'ğ': 'g', 'g': 'ğ', 'Ğ': 'G', 'G': 'Ğ',
            'ı': 'i', 'i': 'ı', 'I': 'İ', 'İ': 'I',
            'ü': 'u', 'u': 'ü', 'Ü': 'U', 'U': 'Ü',
            'ş': 's', 's': 'ş', 'Ş': 'S', 'S': 'Ş',
            'ç': 'c', 'c': 'ç', 'Ç': 'C', 'C': 'Ç'
        }
        variations = {text}
        lower_text = text.lower()
        variations.add(lower_text)
        upper_text = text.upper()
        variations.add(upper_text)
        all_variations = set()
        for variant in variations:
            current_variations = {variant}
            for char in variant:
                if char in char_map:
                    new_variations = set()
                    for v in current_variations:
                        new_variations.add(v.replace(char, char_map[char]))
                    current_variations.update(new_variations)
            all_variations.update(current_variations)
        return all_variations

    if clean_search:
        kodlar_filter = Q(kodlar__icontains=clean_search)
        def clean_code(val):
            return re.sub(r'[^a-zA-Z0-9]', '', val.lower()) if val else ''
        kod_ids = [m.id for m in queryset if clean_code(search_query) in clean_code(m.kod)]
        kod_filter = Q(id__in=kod_ids)
        if search_words:
            ad_filters = []
            for word in search_words:
                word_variations = normalize_azerbaijani_chars(word)
                word_filter = reduce(or_, [Q(adi__icontains=variation) for variation in word_variations])
                firma_filter = reduce(or_, [Q(firma__adi__icontains=variation) for variation in word_variations])
                ad_filters.append(word_filter | firma_filter)
            ad_filter = reduce(and_, ad_filters)
            searchtext_and_filter = reduce(
                and_,
                [reduce(or_, [Q(search_text__icontains=variation) for variation in normalize_azerbaijani_chars(word)]) for word in search_words]
            )
            queryset = queryset.filter(
                kod_filter | kodlar_filter | ad_filter | searchtext_and_filter
            )
        else:
            queryset = queryset.filter(
                kod_filter | kodlar_filter
            )
    return queryset