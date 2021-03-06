# -*- coding: utf-8 -*-
##############################################################################
#
# Copyright (c) 2008-2013 Alistek Ltd (http://www.alistek.com) All Rights Reserved.
#                    General contacts <info@alistek.com>
#
# WARNING: This program as such is intended to be used by professional
# programmers who take the whole responsability of assessing all potential
# consequences resulting from its eventual inadequacies and bugs
# End users who are looking for a ready-to-use solution with commercial
# garantees and support are strongly adviced to contract a Free Software
# Service Company
#
# This program is Free Software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 3
# of the License, or (at your option) any later version.
#
# This module is GPLv3 or newer and incompatible
# with OpenERP SA "AGPL + Private Use License"!
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.
#
##############################################################################

from openerp import models, api, fields, _
from openerp.exceptions import except_orm 
from openerp import netsvc

class report_print_actions(models.TransientModel):
    _name = 'aeroo.print_actions'
    _description = 'Aeroo reports print wizard'

    def check_report(self, report_name):
        if 'report.%s' % report_name not in \
            netsvc.Service._services: # check if report exist in register of reports
            raise except_orm(_('System Error !'),
                             _('Report was not registered in system or deactivated !'))
        return True

    def _reopen(self, res_id, model):
        return {'type': 'ir.actions.act_window',
                'view_mode': 'form',
                'view_type': 'form',
                'res_id': res_id,
                'res_model': self._name,
                'target': 'new',
        }

    def check_if_deferred(self, report_xml, print_ids):
        extras = report_xml.extras.split(',')
        if 'deferred_processing' in extras and report_xml.deferred!='off' and len(print_ids)>=report_xml.deferred_limit:
            return True
        return False

    def start_deferred(self, cr, uid, ids, context=None):
#         this = self.browse(cr, uid, ids[0], context=context)
        report_xml = self.pool.get('ir.actions.report.xml').browse(cr, uid, context['report_action_id'])
        deferred_proc_obj = self.pool.get('deferred_processing.task')
        process_id = deferred_proc_obj.create(cr, uid, {'name':report_xml.name}, context=context)
        deferred_proc_obj.new_process(cr, uid, process_id, context=context)
        print_ids = context.get('active_ids') or []
        deferred_proc_obj.start_process_report(cr, uid, process_id, print_ids, context['report_action_id'], context=context)

        mod_obj = self.pool.get('ir.model.data')
        act_obj = self.pool.get('ir.actions.act_window')

        mod_id = mod_obj.search(cr, uid, [('name', '=', 'action_deferred_processing_task_deferred_processing')])[0]
        res_id = mod_obj.read(cr, uid, mod_id, ['res_id'])['res_id']
        act_win = act_obj.read(cr, uid, res_id, ['name','type','view_id','res_model','view_type', \
                                                'search_view_id','view_mode','target','context'])
        act_win['res_id'] = process_id
        act_win['view_type'] = 'form'
        act_win['view_mode'] = 'form,tree'
        return act_win

    def simple_print(self, cr, uid, ids, context):
        this = self.browse(cr, uid, ids[0], context=context)
        print_ids = context.get('active_ids') or []
        report_xml = self.pool.get('ir.actions.report.xml').browse(cr, uid, context['report_action_id'])
        data = {'model': report_xml.model, 'ids': print_ids, 'id': context['active_id'], 'report_type': 'aeroo'}
        if str(report_xml.out_format.id) != this.out_format:
            report_xml.write({'out_format':this.out_format}, context=context)
        return {
            'type': 'ir.actions.report.xml',
            'report_name': report_xml.report_name,
            'datas': data,
            'context':context
        }

    def to_print(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        this = self.browse(cr, uid, ids[0], context=context)
        report_xml = self.pool.get('ir.actions.report.xml').browse(cr, uid, context['report_action_id'])
        self.check_report(report_xml.report_name)
        print_ids = []
        copies = this.copies
        if copies <= 0:
            print_ids = context.get('active_ids') or []
        else:
            while(copies):
                print_ids.extend(context.get('active_ids') or [])
                copies -= 1
        if str(report_xml.out_format.id) != this.out_format:
            report_xml.write({'out_format':this.out_format}, context=context)
        if self.check_if_deferred(report_xml, print_ids):
            this.write({'state':'confirm','message':_("This process may take too long for interactive processing. \
It is advisable to defer the process in background. \
Do you want to start a deferred process?"),'print_ids':print_ids}, context=context)
            return self._reopen(this.id, this._model)
        ##### Simple print #####
        data = {
                'model': report_xml.model,
                'ids': print_ids,
                'id': context['active_id'],
                'report_type': 'aeroo'
                }
        return {
            'type': 'ir.actions.report.xml',
            'report_name': report_xml.report_name,
            'datas': data,
            'context':context
        }

    @api.model
    def _out_format_get(self):
        obj = self.env['report.mimetypes']
        report_obj = self.env['ir.actions.report.xml']
        report_action_id = self._context.get('report_action_id', False)
        if report_action_id:
            in_format = report_obj.read(report_action_id, ['in_format'])['in_format']
            mimetypes = obj.search([('compatible_types', '=', in_format)])
            return [(x.id, x.name) for x in mimetypes]
        else:
            return []

    out_format = fields.Selection(_out_format_get, 'Output format',
                                  required=True)
    out_format_code = fields.Char('Output format code', size=16,
                                  required=False, readonly=True)
    copies = fields.Integer('Number of copies', required=True)
    message = fields.Text('Message')
    state = fields.Selection([
                              ('draft','Draft'),
                              ('confirm','Confirm'),
                              ('done','Done'),
                              ], 'State', default='draft',
                             select=True, readonly=True)

    def onchange_out_format(self, cr, uid, ids, out_format_id):
        if not out_format_id:
            return {}
        out_format = self.pool.get('report.mimetypes').read(cr, uid, int(out_format_id), ['code'])
        return { 'value':
            {'out_format_code': out_format['code']}
        }

    def _get_default_outformat(self, cr, uid, field, context=None):
        def get_default_outformat(self, cr, uid, context):
            report_action_id = context.get('report_action_id',False)
            if report_action_id:
                report_xml = self.pool.get('ir.actions.report.xml').browse(cr, uid, report_action_id)
                return str(getattr(report_xml.out_format, field))
            else:
                return False
        return get_default_outformat

    def _get_default_number_of_copies(self, cr, uid, context):
        report_action_id = context.get('report_action_id',False)
        if not report_action_id:
            return False
        report_xml = self.pool.get('ir.actions.report.xml').browse(cr, uid, context['report_action_id'])
        return report_xml.copies

    _defaults = {
        'out_format': lambda self, cr, uid, c: self._get_default_outformat(cr, uid, 'id', context),
        'out_format_code': lambda self, cr, uid, c: self._get_default_outformat(cr, uid, 'code', context),
        'copies': _get_default_number_of_copies,
    }

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
