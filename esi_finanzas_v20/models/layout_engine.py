"""Deterministic evaluation of financial definitions, independent of Odoo writes."""
ZERO = (0., 0., 0., 0.)

def add(left, right, factor=1):
    return tuple(a+factor*b for a,b in zip(left,right))

def signed(values, sign):
    # Debit / credit remain the actual movements; only balances change presentation sign.
    return (values[0]*sign,values[1],values[2],values[3]*sign)

def descendant(account, roots, accounts):
    seen=set()
    while account in accounts and account not in seen:
        if account in roots:return True
        seen.add(account);account=accounts[account].get('parent')
    return False


def evaluate_layout(nodes, roots, facts, accounts, order='sequence', max_depth=0, display='movement', tolerance=.005):
    cache, visiting = {}, set()
    def sort_key(key):
        node=nodes[key]
        return (node.get('code',''),node.get('sequence',10),key) if order=='code' else (node.get('sequence',10),node.get('code',''),key)
    children={}
    for key,node in nodes.items():children.setdefault(node.get('parent'),[]).append(key)
    def selected(node, aid):
        if node['mode']=='account_type':return accounts[aid]['type'] in node.get('types',[])
        if node['mode']=='accounts':
            return descendant(aid,set(node.get('accounts',[])),accounts) if node.get('include_children') else aid in node.get('accounts',[])
        return False
    def evaluate(key, exclusions=()):
        if key not in nodes:raise ValueError('La fórmula referencia un título inexistente o no autorizado.')
        node=nodes[key];excluded=tuple(sorted(set(exclusions)|set(node.get('excluded',[]))))
        ck=(key,excluded)
        if ck in cache:return cache[ck]
        # Include only node id in the cycle stack: excluded journals must not mask recursion.
        if key in visiting:raise ValueError('Se detectó un ciclo en fórmulas o referencias financieras.')
        visiting.add(key);value=ZERO;by_account={}
        if node['mode'] in ('accounts','account_type'):
            for fact in facts:
                aid=fact['account']
                if fact['journal'] in excluded or aid not in accounts or not selected(node,aid):continue
                value=add(value,fact['values']);by_account[aid]=add(by_account.get(aid,ZERO),fact['values'])
            if display=='all':
                for aid in accounts:
                    if selected(node,aid):by_account.setdefault(aid,ZERO)
        elif node['mode']=='sum':
            for child in children.get(key,[]):value=add(value,evaluate(child,excluded)[0])
        elif node['mode']=='reference':
            if not node.get('reference'):raise ValueError('Seleccione el título referenciado: '+node['name'])
            value=evaluate(node['reference'],excluded)[0]
        elif node['mode']=='formula':
            for source,factor in node.get('terms',[]):value=add(value,evaluate(source,excluded)[0],factor)
        sign=int(node.get('sign',1));value=signed(value,sign)
        visiting.remove(key);cache[ck]=(value,by_account,excluded)
        return cache[ck]
    def visible(value):
        if display=='all':return True
        if display=='not_zero':return abs(value[3])>=tolerance
        return any(abs(v)>=tolerance for v in value)
    rows=[];printed=set()
    def emit(key,depth,exclusions=()):
        if key in printed:raise ValueError('La jerarquía del informe contiene ciclos o títulos repetidos.')
        printed.add(key);node=nodes[key];value,by_account,excluded=evaluate(key,exclusions)
        if node.get('visible',True) and (not max_depth or depth<=max_depth) and (visible(value) or node['mode']=='formula'):
            rows.append(dict(key='layout:'+str(key),code=node.get('code',''),name=node['name'],depth=depth,
                group=True,style=node.get('style','auto'),opening=value[0],debit=value[1],credit=value[2],closing=value[3],amount=value[3],summary=node['mode']=='formula',excluded_journals=excluded))
            if node.get('detail')!='none' and by_account:
                detail={aid:signed(vals,int(node.get('sign',1))) for aid,vals in by_account.items()}
                if node.get('detail')=='hierarchy':
                    detail_accounts={}
                    for aid in detail:
                        seen=set();current=aid
                        while current in accounts and current not in seen:
                            seen.add(current);detail_accounts[current]=accounts[current];current=accounts[current].get('parent')
                    # Roll up only direct account values, not previously aggregated subtotals.
                    rolled=dict(detail)
                    for aid,vals in detail.items():
                        seen={aid};parent=accounts[aid].get('parent')
                        while parent in detail_accounts and parent not in seen:
                            seen.add(parent);rolled[parent]=add(rolled.get(parent,ZERO),vals);parent=accounts[parent].get('parent')
                    def path(aid,seen=None):
                        seen=set() if seen is None else seen
                        if aid in seen:raise ValueError('Jerarquía circular del plan de cuentas.')
                        seen.add(aid);parent=detail_accounts[aid].get('parent')
                        return (path(parent,seen) if parent in detail_accounts else [])+[detail_accounts[aid]['code']]
                    ordered=sorted(detail_accounts,key=lambda aid:(path(aid),aid))
                    duplicate_codes={accounts[aid]['code'] for aid in detail_accounts if accounts[aid].get('parent') not in detail_accounts and accounts[aid]['code'] and accounts[aid]['code']==node.get('code')}
                    for aid in ordered:
                        account_path=path(aid)
                        if len(account_path)==1 and accounts[aid]['code'] in duplicate_codes:continue
                        level=depth+len(account_path)-sum(code in duplicate_codes for code in account_path);vals=rolled.get(aid,ZERO)
                        if (not max_depth or level<=max_depth) and visible(vals):
                            rows.append(dict(key='detail:%s:%s'%(key,aid),code=accounts[aid]['code'],name=accounts[aid]['name'],depth=level,
                                group=any(a.get('parent')==aid for a in detail_accounts.values()),style='auto',opening=vals[0],debit=vals[1],credit=vals[2],closing=vals[3],amount=vals[3],summary=False,excluded_journals=excluded))
                else:
                    for aid in sorted(detail,key=lambda aid:(accounts[aid]['code'],aid)):
                        vals=detail[aid];level=depth+1
                        if (not max_depth or level<=max_depth) and visible(vals):
                            rows.append(dict(key='detail:%s:%s'%(key,aid),code=accounts[aid]['code'],name=accounts[aid]['name'],depth=level,
                                group=False,style='normal',opening=vals[0],debit=vals[1],credit=vals[2],closing=vals[3],amount=vals[3],summary=False,excluded_journals=excluded))
        for child in sorted(children.get(key,[]),key=sort_key):emit(child,depth+1,excluded)
    # Validate every definition, including hidden helpers, before generating output.
    for key in nodes:evaluate(key)
    for root in sorted(roots,key=sort_key):emit(root,1)
    return rows


def analytic_weight(distribution, selected):
    if not selected:return 1.
    total=0.
    for key,percent in (distribution or {}).items():
        if set(str(key).split(',')) & {str(i) for i in selected}:
            total+=float(percent)/100.
    return min(1.,max(0.,total))


def cashflow_rows(facts,groups,display='movement'):
    """Group liquidity movements without adding parent subtotals twice."""
    direct={};opening=0.;debit=credit=0.
    for fact in facts:
        if fact['opening']:
            opening+=fact['values'][0];continue
        d,c=fact['values'][1:3];debit+=d;credit+=c
        key=fact['group'];direct[key]=add(direct.get(key,ZERO),(0.,d,c,d-c))
    totals=dict(direct)
    for key,values in direct.items():
        seen={key};parent=groups[key].get('parent')
        while parent in groups and parent not in seen:
            seen.add(parent);totals[parent]=add(totals.get(parent,ZERO),values);parent=groups[parent].get('parent')
        if parent in seen:raise ValueError('La jerarquía de cuentas de flujo contiene ciclos.')
    rows=[]
    def row(key,name,depth,values,code='',group=False,summary=False):
        return dict(key='flow:'+str(key),name=name,code=code,depth=depth,group=group,summary=summary,style='heading' if summary else 'auto',
            opening=values[0],debit=values[1],credit=values[2],closing=values[3],amount=values[3])
    rows.append(row('opening','SALDO INICIAL',1,(opening,0.,0.,opening),summary=True,group=True))
    children={}
    for key,value in groups.items():children.setdefault(value.get('parent'),[]).append(key)
    visited=set()
    def emit(key,depth):
        if key in visited:raise ValueError('La jerarquía de cuentas de flujo contiene ciclos.')
        visited.add(key);value=totals.get(key,ZERO);group=groups[key]
        show=display=='all' or (abs(value[3])>=.005 if display=='not_zero' else any(abs(v)>=.005 for v in value))
        if show:rows.append(row(key,group['name'],depth,value,group.get('code',''),bool(children.get(key))))
        for child in sorted(children.get(key,[]),key=lambda c:(groups[c].get('sequence',10),groups[c].get('code',''),str(c))):emit(child,depth+1)
    for key in sorted(children.get(None,[]),key=lambda c:(groups[c].get('sequence',10),str(c))):emit(key,1)
    if len(visited)!=len(groups):raise ValueError('La jerarquía de cuentas de flujo contiene ciclos.')
    rows.append(row('change','CAMBIO NETO',1,(0.,debit,credit,debit-credit),summary=True,group=True))
    rows.append(row('ending','SALDO FINAL',1,(opening,debit,credit,opening+debit-credit),summary=True,group=True))
    return rows
