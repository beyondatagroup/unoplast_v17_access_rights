/** @odoo-module */
/**
 * This file will used to hide the selected options from the form view
 */
import { FormController} from "@web/views/form/form_controller";
import { patch} from "@web/core/utils/patch";
const { onWillStart} = owl;
import {useService} from "@web/core/utils/hooks";
import { NavBar } from '@web/webclient/navbar/navbar';
import { session } from '@web/session';

document.addEventListener("DOMContentLoaded", function() {
    patch(NavBar.prototype,{
        setup() {
            super.setup();
            this.rpc = this.env.services.rpc
            this.currentUser = session.uid;
            this.menu = this.menuService.getAll();
            this.names = this.menu.map(item => item.id);
            this.call_menus();
        },

        async call_menus(){
            var self = this
            var result;
            this.result = await this.env.services.orm.silent.call(
                "res.users",
                "hide_buttons",
            );

            var filteredXmlids = [];

            for (var i = 0; i < this.result.length; i++) {
                this.user_array = [this.result[i].id]
                this.menu_id = this.result[i].menu_ids
                for (var j = 0; j < this.names.length; j++) {
                    if(this.menu_id.includes(this.names[j])){
                        const matchedMenu = this.menu.find(item => item.id === this.names[j]);
                        filteredXmlids.push(matchedMenu.xmlid);
                    }
                }
            }
            function hideSubmenu() {
            const menuItemToHide = document.getElementsByTagName("a");
            const SubmenuItemToHide = document.getElementsByTagName("button");
            for (var x = 0; x < menuItemToHide.length; x++) {
                const dataXmlid = menuItemToHide[x].getAttribute('data-menu-xmlid')
                if (filteredXmlids.includes(dataXmlid)) {
                    menuItemToHide[x].style.display = 'none';
                }
            }

            for (var Y = 0; Y < SubmenuItemToHide.length; Y++) {
                const dataXmlid = SubmenuItemToHide[Y].getAttribute('data-menu-xmlid')
                if (filteredXmlids.includes(dataXmlid)) {
                    SubmenuItemToHide[Y].style.display = 'none';
                }
            }
        }
            document.addEventListener('DOMContentLoaded', hideSubmenu);
            const observer = new MutationObserver(hideSubmenu);
            observer.observe(document.body, { childList: true, subtree: true });
            hideSubmenu();
        return this.menus;
        }
    });
});
