from odoo import api, fields, models



class MrpProductionBackorder(models.TransientModel):
    _inherit = 'mrp.production.backorder'

    _description = "Wizard to mark as done or Record Production"


    shift_type = fields.Selection([('shift_1', 'Shift 1'), ('shift_2', 'Shift 2'), ('shift_3', 'Shift 3')],
                                  string="Shift", copy=False,readonly=True,store=True)

    product_qty = fields.Float(
        'Quantity To Produce', digits='Product Unit of Measure',
        readonly=True, required=True,
        store=True, copy=True)



    @api.model
    def default_get(self, fields):

        res = super(MrpProductionBackorder, self).default_get(fields)
        active_id = self.env.context.get('active_id')
        # record = self.env['mrp.production'].browse(active_id)
        print("\n\n.......record.....self.....",self)

        if active_id:
            record = self.env['mrp.production'].search([('id', '=', active_id)])
            print('record:>>>>', record)

            last_records = self.env['mrp.production'].search([
                ('id', 'in', record.procurement_group_id.mrp_production_ids.ids),
                ('state', '=', 'progress')
            ])
            print('?????????????????????????????', last_records)

            print('\n\n>>>>>>>>>>>>record.qty_producing>>>>>>>>>', last_records.qty_producing)
            print('\n\n>>>>>>>>>>>>record.shift_type>>>>>>>>>>>>', last_records.shift_type)

            res.update({'product_qty': last_records.qty_producing or last_records.qty_produced,
                        'shift_type': last_records.shift_type})
        return res



    def action_backorder(self):
        print("\n\n..............._create_update_move_finished...............", self)
        print("\n\n...............self.env.context.get...........", self.env.context)
        res = super(MrpProductionBackorder, self).action_backorder()
        active_id = self.env.context.get('active_id')
        print("\n\n...............active_id...............", active_id)

        if active_id:
            record = self.env['mrp.production'].search([('id', '=', active_id)])

            records = self.env['mrp.production'].search([
                ('id', 'in', record.procurement_group_id.mrp_production_ids.ids),
                ('state', '=', 'done')
            ])
            print("\n\n\n...........1111111111111111.........record..................", record)
            print("\n\n\n....................records..................", records)

            last_records = self.env['mrp.production'].search([
                ('id', 'in', record.procurement_group_id.mrp_production_ids.ids),
                ('state', '=', 'confirmed')
            ])
            print('\n\n???????????last_records??????????????????', last_records)

            main_vals = []
            for req in records:
                print("\n...req.....",req.shift_type)
                for data in req.move_finished_ids:
                    vals = {
                        'product_id': data.product_id.id,
                        'product_uom_qty': data.product_uom_qty,
                        'data': data.product_uom_qty,
                        'quantity': data.quantity,
                        'product_uom': data.product_uom.id,
                        'location_id': data.location_id.id,
                        'location_dest_id': data.location_dest_id.id,
                        'name': data.name,
                        'shift_type': req.shift_type,
                        'date_finished': req.date_finished
                    }
                    main_vals.append(vals)

                    print(">>>>>>>>>>>>>main_vals:>>>>>>>>>>>>>>>>>>", main_vals)

            for m_v in main_vals:
                last_records.finished_product_ids.sudo().create({
                    'product_id': m_v['product_id'],
                    'product_uom_qty': m_v['product_uom_qty'],
                    'quantity': m_v['quantity'],
                    'product_uom': m_v['product_uom'],
                    'move_product_id': last_records.id,
                    'location_id': m_v['location_id'],
                    'location_dest_id': m_v['location_dest_id'],
                    'name': m_v['name'],
                    'shift_type': m_v['shift_type'],
                    'state': 'done',
                    'date_deadline': m_v['date_finished']
                    })
            print("\n\n\nooooooooooooo.............",last_records.move_finished_ids)
            produce_all_data = last_records.move_finished_ids
            print("\n\n\nooooooooooooo.........11111111....",produce_all_data)
            for p_all in produce_all_data:
                produce_all_data_dict = {
                    'product_id': (p_all.product_id.id),
                    'product_uom_qty': p_all.product_uom_qty,
                    'data': p_all.product_uom_qty,
                    'quantity': p_all.quantity,
                    'product_uom': p_all.product_uom.id,
                    'location_id': p_all.location_id.id,
                    'location_dest_id': p_all.location_dest_id.id,
                    'name': p_all.name,
                    'shift_type': self.shift_type,
                    'date_finished': last_records.date_finished
                }
                print("\n\n\nooooooooooooo.........produce_all_data_dict....",produce_all_data_dict)

                last_records.finished_product_ids.sudo().create({
                    'product_id': produce_all_data_dict['product_id'],
                    'product_uom_qty': produce_all_data_dict['product_uom_qty'],
                    'quantity': produce_all_data_dict['quantity'],
                    'product_uom': produce_all_data_dict['product_uom'],
                    'move_product_id': last_records.id,
                    'location_id': produce_all_data_dict['location_id'],
                    'location_dest_id': produce_all_data_dict['location_dest_id'],
                    'name': produce_all_data_dict['name'],
                    'shift_type': produce_all_data_dict['shift_type'],
                    'state': 'confirmed',
                    'date_deadline': produce_all_data_dict['date_finished']
                })
        return res

