# -*- coding: utf-8 -*-
import json
from odoo import http
from odoo.http import request


class PartnerMapController(http.Controller):

    @http.route('/partner/map', type='http', auth='user')
    def partner_map(self, partner_ids=None, **kwargs):
        """Affiche une carte OpenStreetMap avec les contacts"""
        if not partner_ids:
            return request.render('is_fromtome14.partner_map_empty')

        # Récupérer les contacts
        try:
            partner_ids_list = [int(id) for id in partner_ids.split(',') if id]
            partners = request.env['res.partner'].browse(partner_ids_list)
        except (ValueError, AttributeError):
            return request.render('is_fromtome14.partner_map_empty')

        # Filtrer les contacts avec localisation
        partners_with_location = partners.filtered(lambda p: p.is_localisation)

        if not partners_with_location:
            return request.render('is_fromtome14.partner_map_empty')

        # Préparer les données pour la carte
        markers = []
        for partner in partners_with_location:
            try:
                lat, lng = partner.is_localisation.split(',')
                markers.append({
                    'lat': float(lat.strip()),
                    'lng': float(lng.strip()),
                    'name': partner.name or '',
                    'adresse': partner.contact_address or '',
                })
            except (ValueError, AttributeError):
                continue

        if not markers:
            return request.render('is_fromtome14.partner_map_empty')

        # Calculer le centre de la carte
        center_lat = sum(m['lat'] for m in markers) / len(markers)
        center_lng = sum(m['lng'] for m in markers) / len(markers)

        # Calculer le zoom adapté
        if len(markers) == 1:
            zoom = 15
        else:
            lats = [m['lat'] for m in markers]
            lngs = [m['lng'] for m in markers]
            lat_diff = max(lats) - min(lats)
            lng_diff = max(lngs) - min(lngs)
            max_diff = max(lat_diff, lng_diff)

            if max_diff > 5:
                zoom = 7
            elif max_diff > 2:
                zoom = 8
            elif max_diff > 1:
                zoom = 9
            elif max_diff > 0.5:
                zoom = 10
            elif max_diff > 0.1:
                zoom = 11
            else:
                zoom = 12

        js_code = f"""
            var map = L.map('map').setView([{center_lat}, {center_lng}], {zoom});

            // Couche carte normale
            var osmLayer = L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
                attribution: '© OpenStreetMap contributors',
                maxZoom: 19
            }});

            // Couche satellite
            var satelliteLayer = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{{z}}/{{y}}/{{x}}', {{
                attribution: '© Esri',
                maxZoom: 19
            }});

            osmLayer.addTo(map);

            var baseMaps = {{
                "Carte": osmLayer,
                "Satellite": satelliteLayer
            }};
            L.control.layers(baseMaps).addTo(map);

            var markers = {json.dumps(markers)};

            markers.forEach(function(marker) {{
                var popupContent = '<div class="popup-title">' + marker.name + '</div>';
                if (marker.adresse) {{
                    popupContent += '<div class="popup-info"><strong>Adresse:</strong> ' + marker.adresse + '</div>';
                }}
                popupContent += '<div class="popup-info"><strong>GPS:</strong> ' + marker.lat + ', ' + marker.lng + '</div>';

                L.marker([marker.lat, marker.lng])
                    .addTo(map)
                    .bindPopup(popupContent);
            }});
        """

        return request.render('is_fromtome14.partner_map_view', {
            'markers': markers,
            'js_code': js_code,
        })
