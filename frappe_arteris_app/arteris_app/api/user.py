import frappe


def create_new_role(role_name, description=None, desk_access=1):
    """Cria uma nova role no sistema"""
    
    try:
        # Verificar se a role já existe
        if frappe.db.exists("Role", role_name):
            return {"status": "error", "message": f"Role '{role_name}' já existe"}
        
        # Criar a nova role
        role_doc = frappe.get_doc({
            "doctype": "Role",
            "role_name": role_name,
            "desk_access": desk_access,
            "description": description or f"Role personalizada: {role_name}"
        })
        
        role_doc.insert()
        frappe.db.commit()
        
        return {"status": "success", "message": f"Role '{role_name}' criada com sucesso"}
    
    except Exception as e:
        frappe.log_error(f"Erro ao criar role: {str(e)}")
        return {"status": "error", "message": str(e)}

def remove_doctype_permissions(doctype_name, role_name):
    """
    Remove permissão de uma role de um DocType
    """
    try:
        doctype_doc = frappe.get_doc("DocType", doctype_name)
        
        # Encontrar o índice da permissão a ser removida
        perm_to_remove = None
        for i, perm in enumerate(doctype_doc.permissions):
            if perm.role == role_name:
                perm_to_remove = i
                break
        
        # Remover usando pop() com o índice
        if perm_to_remove is not None:
            doctype_doc.permissions.pop(perm_to_remove)
            doctype_doc.save()
            frappe.db.commit()
            print(f"✅ Permissão da role '{role_name}' removida do DocType '{doctype_name}'")
        else:
            print(f"⚠️ Role '{role_name}' não encontrada no DocType '{doctype_name}'")
            
    except Exception as e:
        frappe.log_error(f"Erro ao configurar permissões: {str(e)}")
        return {"status": "error", "message": str(e)}    

def set_doctype_permissions(doctype_name, role_name, permissions):
    """
    Configura permissões de uma role para um DocType específico
    
    permissions = {
        "read": 1,
        "write": 1,
        "create": 1,
        "delete": 0,
        "submit": 0,
        "cancel": 0,
        "amend": 0,
        "report": 1,
        "import": 0,
        "export": 1,
        "print": 1,
        "email": 1,
        "set_user_permissions": 0
    }
    """
    
    try:
        
        # Buscar DocType
        doctype_doc = frappe.get_doc("DocType", doctype_name)
        
        # Verificar se já existe permissão para esta role
        existing_perm = None
        for perm in doctype_doc.permissions:
            if perm.role == role_name:
                existing_perm = perm
                break

        submit = 0
        cancel = 0
        amend = 0
        # Verifica se o doctype é submetível
        if not doctype_doc.is_submittable:
            if permissions["submit"] == 1:
                submit = 1
            if permissions["cancel"] == 1:
                cancel = 1
            if permissions["amend"] == 1:
                amend = 1
            print(f"DocType {doctype_name} não é submetível. Ajustando permissão de submit para 0.")
            permissions["submit"] = 0
            permissions["cancel"] = 0
            permissions["amend"] = 0
        
        if existing_perm:
            # Atualizar permissões existentes
            for key, value in permissions.items():
                if hasattr(existing_perm, key):
                    setattr(existing_perm, key, value)
        else:
            # Criar nova permissão
            new_perm = {
                "role": role_name,
                "permlevel": 0,  # Nível de permissão padrão
                **permissions
            }
            doctype_doc.append("permissions", new_perm)
        
        # Salvar as alterações
        doctype_doc.save()
        frappe.db.commit()

        permissions["submit"] = submit
        permissions["cancel"] = submit
        
        return {"status": "success", "message": f"Permissões configuradas para {role_name} no DocType {doctype_name}"}
    
    except Exception as e:
        frappe.log_error(f"Erro ao configurar permissões: {str(e)}")
        return {"status": "error", "message": str(e)}

def set_user_role(user_email, role_name):
    """Define apenas uma função para um usuário específico"""
    
    # Buscar o documento do usuário
    user_doc = frappe.get_doc("User", user_email)
    
    # Limpar todas as funções existentes
    user_doc.role_profiles = []
    user_doc.roles = []
    user_doc.default_app = 'arteris_app'
    user_doc.default_workspace = 'MSI'
    user_doc.module_profile = 'BM'

    # Adicionar apenas a função desejada
    user_doc.append("roles", {
        "role": role_name,
    })
    if not role_name == "Operador":
        user_doc.append("roles", {
            "role": "Operador",
        })
    
    # Salvar as alterações
    user_doc.save(ignore_permissions=True)
    frappe.db.commit()
    
    return {"success": True, "message": f"Função {role_name} atribuída ao usuário {user_email}"}        

@frappe.whitelist(methods=["POST"])
def update_doctypes():

    create_new_role("Operador", "Inclui e altera cadastros |inclui e submete medições manuais", 1)
    create_new_role("Gerente", "Inclui e altera cadastros | inclui, submete e cancela medições manuais", 1)
    create_new_role("Administrador", "Inclui,altera e exclui cadastros |inclui, submete e cancela medições manuais", 1)
    create_new_role("Administrador Global", "Todas as permissões incluindo edição da plataforma (Desenvolvimento)", 1)

    doctypes = frappe.db.sql("""
        SELECT
            name,
            module
        FROM
            `tabDocType`
        """,
    as_dict=True)
    print(doctypes)

    # Operador
    role_ooperador = {
        "read": 1,
        "write": 1,
        "create": 1,
        "submit": 1,
        "cancel": 0,
        "delete": 0,
        "amend": 0,
        "report": 0,
        "export": 0,
        "import": 0,
        "share": 0,
        "print": 0,
        "email": 0,
        "if_owner": 0,
        "select": 0            
    }
        
    # Geremte
    role_grerente = {
        "read": 1,
        "write": 1,
        "create": 1,
        "submit": 1,
        "cancel": 1,
        "delete": 0,
        "amend": 0,
        "report": 0,
        "export": 0,
        "import": 0,
        "share": 0,
        "print": 0,
        "email": 0,
        "if_owner": 0,
        "select": 0            
    }

        # Administrador
    
    # Administrador
    role_administrador = {
        "read": 1,
        "write": 1,
        "create": 1,
        "submit": 1,
        "cancel": 1,
        "delete": 1,
        "amend": 0,
        "report": 0,
        "export": 0,
        "import": 0,
        "share": 0,
        "print": 0,
        "email": 0,
        "if_owner": 0,
        "select": 0            
    }

        # Administrador Global
    
    # Administrador Global
    role_global = {
        "read": 1,
        "write": 1,
        "create": 1,
        "submit": 1,
        "cancel": 1,
        "delete": 1,
        "amend": 1,
        "report": 1,
        "export": 1,
        "import": 0,
        "share": 1,
        "print": 1,
        "email": 1,
        "if_owner": 0,
        "select": 1            
    }        

    try:
        for d in doctypes:
            if d.module == 'Arteris':
                set_doctype_permissions(d.name, "Operador", role_ooperador)
                set_doctype_permissions(d.name, "Gerente", role_grerente)
                set_doctype_permissions(d.name, "Administrador", role_administrador)
            else:
                remove_doctype_permissions(d.name, "Operador")
                remove_doctype_permissions(d.name, "Gerente")
                remove_doctype_permissions(d.name, "Administrador")
            set_doctype_permissions(d.name, "Administrador Global", role_global)

    except Exception as e:
        frappe.log_error(f"Erro ao atualizar permissões: {str(e)}")
        return {"status": "error", "message": str(e)}

    # Aplicar funcao
    users = [
        {'email': 'adriana.lanconi@arteris.com.br', 'role': 'Operador'},
        {'email': 'adriana.santos@arteris.com.br', 'role': 'Gerente'},
        {'email': 'afonso.lima@arteris.com.br', 'role': 'Operador'},
        {'email': 'alan.hilario@arteris.com.br', 'role': 'Operador'},
        {'email': 'alessandra.kazmiercz@arteris.com.br', 'role': 'Operador'},
        {'email': 'alex.costa@concremat.com.br', 'role': 'Operador'},
        {'email': 'alexandre.capozzi@arteris.com.br', 'role': 'Operador'},
        {'email': 'aline.santos@arteris.com.br', 'role': 'Operador'},
        {'email': 'alisson.drewnicki@arteris.com.br', 'role': 'Operador'},
        {'email': 'amanda.mata.est@arteris.com.br', 'role': 'Operador'},
        {'email': 'amanda.reus@arteris.com.br', 'role': 'Operador'},
        {'email': 'ana.correia@arteris.com.br', 'role': 'Operador'},
        {'email': 'ana.lopes@arteris.com.br', 'role': 'Operador'},
        {'email': 'ana.moura@arteris.com.br', 'role': 'Operador'},
        {'email': 'ana.parreira@arteris.com.br', 'role': 'Operador'},
        {'email': 'angelica.antonio@arteris.com.br', 'role': 'Operador'},
        {'email': 'angelica.sprotte@arteris.com.br', 'role': 'Operador'},
        {'email': 'arthur.sartore@arteris.com.br', 'role': 'Operador'},
        {'email': 'aureo.vale@arteris.com.br', 'role': 'Administrador Global'},
        {'email': 'beatriz.santos@arteris.com.br', 'role': 'Operador'},
        {'email': 'bianca.dasilva@arteris.com.br', 'role': 'Operador'},
        {'email': 'brenda.machado@arteris.com.br', 'role': 'Operador'},
        {'email': 'bruna.freitas@arteris.com.br', 'role': 'Operador'},
        {'email': 'bruna.nagel@arteris.com.br', 'role': 'Gerente'},
        {'email': 'bruno.braga.est@arteris.com.br', 'role': 'Gerente'},
        {'email': 'bruno.teixeira@arteris.com.br', 'role': 'Operador'},
        {'email': 'camila.junkes@arteris.com.br', 'role': 'Operador'},
        {'email': 'camila.reis@arteris.com.br', 'role': 'Operador'},
        {'email': 'carlos.pavan@arteris.com.br', 'role': 'Operador'},
        {'email': 'carlos.pires@arteris.com.br', 'role': 'Operador'},
        {'email': 'carolina.santos.ter@arteris.com.br', 'role': 'Operador'},
        {'email': 'cassio.conci@arteris.com.br', 'role': 'Operador'},
        {'email': 'cristiano.bertozzi@arteris.com.br', 'role': 'Gerente'},
        {'email': 'daniel.morais@arteris.com.br', 'role': 'Operador'},
        {'email': 'danilo.oliveira@arteris.com.br', 'role': 'Operador'},
        {'email': 'dayanne.furtado@arteris.com.br', 'role': 'Operador'},
        {'email': 'denise.pacheco@arteris.com.br', 'role': 'Operador'},
        {'email': 'diego.lima@arteris.com.br', 'role': 'Operador'},
        {'email': 'diogo.santos@arteris.com.br', 'role': 'Operador'},
        {'email': 'dyego.bracht@arteris.com.br', 'role': 'Administrador Global'},
        {'email': 'edivaldo.braga@arteris.com.br', 'role': 'Gerente'},
        {'email': 'edson.risso@arteris.com.br', 'role': 'Gerente'},
        {'email': 'eduarda.beraldo@arteris.com.br', 'role': 'Operador'},
        {'email': 'eliane.santos@arteris.com.br', 'role': 'Operador'},
        {'email': 'ellen.santos@arteris.com.br', 'role': 'Operador'},
        {'email': 'engos.schneider@arteris.com.br', 'role': 'Operador'},
        {'email': 'erica.pires@arteris.com.br', 'role': 'Operador'},
        {'email': 'eugenio.miranda@arteris.com.br', 'role': 'Gerente'},
        {'email': 'evelin.assis@arteris.com.br', 'role': 'Operador'},
        {'email': 'fabiano.rodrigues@arteris.com.br', 'role': 'Operador'},
        {'email': 'fabio.domingues@arteris.com.br', 'role': 'Operador'},
        {'email': 'felipe.calsavara@arteris.com.br', 'role': 'Operador'},
        {'email': 'felipe.ferreira@arteris.com.br', 'role': 'Gerente'},
        {'email': 'felipe.schafhauser@arteris.com.br', 'role': 'Operador'},
        {'email': 'fernando.possari@arteris.com.br', 'role': 'Operador'},
        {'email': 'fernando.rosim@arteris.com.br', 'role': 'Operador'},
        {'email': 'filipe.pereira@arteris.com.br', 'role': 'Operador'},
        {'email': 'francine.coppola@arteris.com.br', 'role': 'Operador'},
        {'email': 'gabriela.dias@arteris.com.br', 'role': 'Operador'},
        {'email': 'gabriela.souza@arteris.com.br', 'role': 'Operador'},
        {'email': 'geovany.tavares@arteris.com.br', 'role': 'Gerente'},
        {'email': 'gilberto.fixfex@arteris.com.br', 'role': 'Gerente'},
        {'email': 'giovana.pereira@arteris.com.br', 'role': 'Gerente'},
        {'email': 'gislane.silva@arteris.com.br', 'role': 'Operador'},
        {'email': 'giuliano.soares@arteris.com.br', 'role': 'Operador'},
        {'email': 'graziele.alves@arteris.com.br', 'role': 'Gerente'},
        {'email': 'guilherme.dias@arteris.com.br', 'role': 'Operador'},
        {'email': 'guilherme.gomes@arteris.com.br', 'role': 'Operador'},
        {'email': 'guilherme.munhoz@arteris.com.br', 'role': 'Gerente'},
        {'email': 'gustavo.alcoforado@arteris.com.br', 'role': 'Operador'},
        {'email': 'gustavo.rubira@arteris.com.br', 'role': 'Gerente'},
        {'email': 'gustavo.tavares@arteris.com.br', 'role': 'Operador'},
        {'email': 'heitor.fazan.est@arteris.com.br', 'role': 'Operador'},
        {'email': 'igor.mello@arteris.com.br', 'role': 'Operador'},
        {'email': 'ilizani.paz@arteris.com.br', 'role': 'Operador'},
        {'email': 'isabella.neves@nucleoengenharia.com.br', 'role': 'Operador'},
        {'email': 'janaina.dutra@arteris.com.br', 'role': 'Operador'},
        {'email': 'jane.volani@arteris.com.br', 'role': 'Operador'},
        {'email': 'jaqueline.boroto@arteris.com.br', 'role': 'Operador'},
        {'email': 'jessica.bonaldi@arteris.com.br', 'role': 'Operador'},
        {'email': 'joao.azevedo@arteris.com.br', 'role': 'Operador'},
        {'email': 'joao.langer@arteris.com.br', 'role': 'Operador'},
        {'email': 'joao.azevedo@arteris.com.br', 'role': 'Gerente'},
        {'email': 'johnata.silva@arteris.com.br', 'role': 'Operador'},
        {'email': 'jose.fischer@arteris.com.br', 'role': 'Operador'},
        {'email': 'jose.pereira@arteris.com.br', 'role': 'Operador'},
        {'email': 'josegledson.silva@arteris.com.br', 'role': 'Operador'},
        {'email': 'josue.pacheco@arteris.com.br', 'role': 'Operador'},
        {'email': 'julia.costa.est@arteris.com.br', 'role': 'Gerente'},
        {'email': 'jun.takahashi@arteris.com.br', 'role': 'Operador'},
        {'email': 'kamilly.floor.est@arteris.com.br', 'role': 'Operador'},
        {'email': 'kaue.britto@arteris.com.br', 'role': 'Operador'},
        {'email': 'keila.oyama@arteris.com.br', 'role': 'Operador'},
        {'email': 'kenia.thomazi@arteris.com.br', 'role': 'Gerente'},
        {'email': 'larissa.dias@arteris.com.br', 'role': 'Gerente'},
        {'email': 'leonardo.benito@arteris.com.br', 'role': 'Operador'},
        {'email': 'leonardo.silva@arteris.com.br', 'role': 'Operador'},
        {'email': 'leticia.arantes@arteris.com.br', 'role': 'Operador'},
        {'email': 'leticia.carmo@arteris.com.br', 'role': 'Operador'},
        {'email': 'lorrayne.lopes@arteris.com.br', 'role': 'Operador'},
        {'email': 'lucas.gomes@arteris.com.br', 'role': 'Operador'},
        {'email': 'lucas.ribeiro@arteris.com.br', 'role': 'Operador'},
        {'email': 'luciana.carvalho@arteris.com.br', 'role': 'Operador'},
        {'email': 'luiz.gomes@arteris.com.br', 'role': 'Operador'},
        {'email': 'luiz.tomasoni@arteris.com.br', 'role': 'Operador'},
        {'email': 'luizfilipi.silva@arteris.com.br', 'role': 'Operador'},
        {'email': 'marcelo.olibratoski@arteris.com.br', 'role': 'Operador'},
        {'email': 'marcio.bianchi@arteris.com.br', 'role': 'Operador'},
        {'email': 'marcoantonio.reis@arteris.com.br', 'role': 'Operador'},
        {'email': 'maria.chiamolera@arteris.com.br', 'role': 'Gerente'},
        {'email': 'mariana.cillo@arteris.com.br', 'role': 'Operador'},
        {'email': 'mariana.pereira@arteris.com.br', 'role': 'Gerente'},
        {'email': 'jose.fischer@arteris.com.br', 'role': 'Operador'},
        {'email': 'jose.pereira@arteris.com.br', 'role': 'Operador'},
        {'email': 'josegledson.silva@arteris.com.br', 'role': 'Operador'},
        {'email': 'josue.pacheco@arteris.com.br', 'role': 'Operador'},
        {'email': 'julia.costa.est@arteris.com.br', 'role': 'Gerente'},
        {'email': 'jun.takahashi@arteris.com.br', 'role': 'Operador'},
        {'email': 'kamilly.floor.est@arteris.com.br', 'role': 'Operador'},
        {'email': 'kaue.britto@arteris.com.br', 'role': 'Operador'},
        {'email': 'keila.oyama@arteris.com.br', 'role': 'Operador'},
        {'email': 'kenia.thomazi@arteris.com.br', 'role': 'Gerente'},
        {'email': 'larissa.dias@arteris.com.br', 'role': 'Gerente'},
        {'email': 'leonardo.benito@arteris.com.br', 'role': 'Operador'},
        {'email': 'leonardo.silva@arteris.com.br', 'role': 'Operador'},
        {'email': 'leticia.arantes@arteris.com.br', 'role': 'Operador'},
        {'email': 'leticia.carmo@arteris.com.br', 'role': 'Operador'},
        {'email': 'lorrayne.lopes@arteris.com.br', 'role': 'Operador'},
        {'email': 'lucas.gomes@arteris.com.br', 'role': 'Operador'},
        {'email': 'lucas.ribeiro@arteris.com.br', 'role': 'Operador'},
        {'email': 'luciana.carvalho@arteris.com.br', 'role': 'Operador'},
        {'email': 'luiz.gomes@arteris.com.br', 'role': 'Operador'},
        {'email': 'luiz.tomasoni@arteris.com.br', 'role': 'Operador'},
        {'email': 'luizfilipi.silva@arteris.com.br', 'role': 'Operador'},
        {'email': 'marcelo.olibratoski@arteris.com.br', 'role': 'Operador'},
        {'email': 'marcio.bianchi@arteris.com.br', 'role': 'Operador'},
        {'email': 'marcoantonio.reis@arteris.com.br', 'role': 'Operador'},
        {'email': 'maria.chiamolera@arteris.com.br', 'role': 'Gerente'},
        {'email': 'mariana.cillo@arteris.com.br', 'role': 'Operador'},
        {'email': 'mariana.pereira@arteris.com.br', 'role': 'Gerente'},
        {'email': 'mariele.dias@arteris.com.br', 'role': 'Operador'},
        {'email': 'marinilce.perosso@arteris.com.br', 'role': 'Operador'},
        {'email': 'mateus.wobeto@arteris.com.br', 'role': 'Operador'},
        {'email': 'maycon.conceicao@arteris.com.br', 'role': 'Gerente'},
        {'email': 'michele.frohlich@arteris.com.br', 'role': 'Operador'},
        {'email': 'pamela.constante@arteris.com.br', 'role': 'Gerente'},
        {'email': 'patricia.oliveira@arteris.com.br', 'role': 'Operador'},
        {'email': 'paulo.volpi@arteris.com.br', 'role': 'Gerente'},
        {'email': 'pedro.lopes@arteris.com.br', 'role': 'Gerente'},
        {'email': 'rebeca.garcia@arteris.com.br', 'role': 'Gerente'},
        {'email': 'rodrigo.bevilaqua@arteris.com.br', 'role': 'Operador'},
        {'email': 'rodrigo.brych@arteris.com.br', 'role': 'Gerente'},
        {'email': 'rodrigo.machado@arteris.com.br', 'role': 'Gerente'},
        {'email': 'saulo.souza@arteris.com.br', 'role': 'Operador'},
        {'email': 'sueli.mota@arteris.com.br', 'role': 'Gerente'},
        {'email': 'suzann.marins@arteris.com.br', 'role': 'Operador'},
        {'email': 'taciana.bordon@arteris.com.br', 'role': 'Operador'},
        {'email': 'tania.ziquiel@arteris.com.br', 'role': 'Gerente'},
        {'email': 'tassiara.menegatti@arteris.com.br', 'role': 'Operador'},
        {'email': 'thiago.evaristo@arteris.com.br', 'role': 'Operador'},
        {'email': 'thiago.leite@arteris.com.br', 'role': 'Operador'},
        {'email': 'thiago.santos@arteris.com.br', 'role': 'Gerente'},
        {'email': 'uilian.inacio@arteris.com.br', 'role': 'Operador'},
        {'email': 'vicente.teixeira@arteris.com.br', 'role': 'Operador'},
        {'email': 'vinicius.chapim@arteris.com.br', 'role': 'Gerente'},
        {'email': 'vinicius.lourenco@arteris.com.br', 'role': 'Gerente'},
        {'email': 'vinicius.matos@arteris.com.br', 'role': 'Operador'},
        {'email': 'vinicius.uso@arteris.com.br', 'role': 'Operador'},
        {'email': 'vitoria.cruz.est@arteris.com.br', 'role': 'Operador'},
        {'email': 'walder.lima@arteris.com.br', 'role': 'Operador'}]

    for user in users:
        try:
            set_user_role(user['email'], user['role'])
        except Exception as e:
            print(f"Error setting role for {user['email']}: {e}")

    return {"status": "success", "message": "Permissões atualizadas para todos os DocTypes do módulo Arteris"}