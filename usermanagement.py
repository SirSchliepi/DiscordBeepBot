class UserManagement:
    QUIZ_BOT_OWNER = 20
    QUIZ_BOT_ADMIN = 50
    QUIZ_SERVER_OWNER = 80
    QUIZ_SERVER_ADMIN = 100
    QUIZ_SERVER_MODERATOR =150
    USER = 250
    
    DESC = {QUIZ_BOT_OWNER: 'Bot Owner', QUIZ_BOT_ADMIN: 'Bot Admin', QUIZ_SERVER_OWNER: 'Owner',
            QUIZ_SERVER_ADMIN: 'Admin', QUIZ_SERVER_MODERATOR: 'Moderator', USER: 'User' }
    
    def __init__(self, userdb=None):
        
        if not userdb:
            userdb = {"global" : {"admin":[], "owner":[]}, "guilds" :{}}
            userdb["global"]["owner"].append(776507216755949580)
        
        
        self.privs = userdb
        
        
    def check_if_mod(self, guild, user):
        return self.check_privilege(guild, user)<=UserManagement.QUIZ_SERVER_MODERATOR
    
    def check_if_admin(self, guild, user):
        return self.check_privilege(guild, user)<=UserManagement.QUIZ_SERVER_ADMIN
    
    def check_if_owner(self, guild, user):
        return self.check_privilege(guild, user)<=UserManagement.QUIZ_SERVER_OWNER
    
    def get_user_db(self):
        return self.privs
    
    def grant(self, guild, from_user, to_user, type):
        erg = {"msg": ""}
        
        from_lvl = self.check_privilege(guild, from_user)
        to_lvl = self.check_privilege(guild, to_user)
 
        if from_lvl >= UserManagement.USER:
            erg["msg"] = "Deine Berechtigungen genügen nicht diesen Befehl auszuführen."
            return erg

        if to_lvl <= from_lvl: 
            erg["msg"] = "Ziel besitzt bereits höhere oder gleiche Berechtigung."
            return erg
        
        if type <= from_lvl:
            erg["msg"] = "Berechtigungen können nur unterhalb der eigenen Stufe erteilt werden."
            return erg
        
        if from_user==to_user:
            erg["msg"] = "Die eigenen Berechtigungen können nicht geändert werden."
            return erg
        
        if type == UserManagement.QUIZ_BOT_ADMIN:
            self.revoke(None,to_user,"global")
            self.privs["global"]["admin"].append(to_user)
            erg["msg"] = "Die Berechtigung wurde erfolgreich vergeben."
            return erg   
        elif type == UserManagement.QUIZ_BOT_OWNER:
            self.revoke(None,to_user,"global")
            self.privs["global"]["owner"].append(to_user)
            erg["msg"] = "Die Berechtigung wurde erfolgreich vergeben."
            return erg
        elif type == UserManagement.USER:
            self.revoke(None,to_user,"global")
            erg["msg"] = "Die Berechtigung wurde erfolgreich vergeben."
            return erg
        
        if not guild:
            erg["msg"] = "Server ist nicht bekannt. Befehl muss auf einem Server ausgeführt werden."
            return erg
        
        if guild.id not in self.privs["guilds"]:
            self.privs["guilds"][guild.id] = {"owner": [], "admin": [], "mod":[]}
            
        self.revoke(guild,to_user,"guild")
        
        gpriv = self.privs["guilds"][guild.id]
        if type == UserManagement.QUIZ_SERVER_OWNER:
            gpriv["owner"].append(to_user)
        if type == UserManagement.QUIZ_SERVER_ADMIN:
            gpriv["admin"].append(to_user)
        if type == UserManagement.QUIZ_SERVER_MODERATOR:
            gpriv["mod"].append(to_user)

        
        erg["msg"] = "Die Berechtigung wurde erfolgreich vergeben."
        return erg
        
            
    def revoke(self, guild, user, target):
        if not user:
            return 
        userid = user
        if not isinstance(user, int):
            userid = user.id
            
        if target=="global":
            for x in ["admin","owner"]: 
                if userid in self.privs["global"][x]: self.privs["global"][x].remove(userid)
            for g in self.privs["guilds"]:
                for x in ["owner","admin","mod"]:
                    if userid in self.privs["guilds"][g][x]: 
                        self.privs["guilds"][g][x].remove(userid)

        if target=="guild":
            if not guild: return 

            mpriv = self.privs["guilds"]        
            if guild.id not in mpriv:
                return 
            
            gpriv = self.privs["guilds"][guild.id]
            for x in ["owner","admin","mod"]:
                if userid in gpriv[x]: gpriv[x].remove(userid)
            
    
    
    def check_privilege(self, guild, user):
        if not user:
            return self.USER

        userid = user
        if not isinstance(user, int):
            userid = user.id
        
        if userid in self.privs["global"]["owner"]: return UserManagement.QUIZ_BOT_OWNER
        if userid in self.privs["global"]["admin"]: return UserManagement.QUIZ_BOT_ADMIN
        
        if not isinstance(user, int):
            roles = []
            if hasattr(user,'roles'):
                roles = [str(r) for r in user.roles]
            if 'QuizBotAdmin' in roles:
                return UserManagement.QUIZ_SERVER_ADMIN
            if 'QuizBotMod' in roles:
                return UserManagement.QUIZ_SERVER_MODERATOR
        
        if not guild:
            return self.USER
    
        guildid = guild
        if not isinstance(guild, str) and not isinstance(guild, int):
            guildid = guild.id

        
        mpriv = self.privs["guilds"]
        
        if guildid not in mpriv:
            return self.USER
        
        gpriv = self.privs["guilds"][guildid]
        
        if userid in gpriv["owner"]: return UserManagement.QUIZ_SERVER_OWNER
        if userid in gpriv["admin"]: return UserManagement.QUIZ_SERVER_ADMIN
        if userid in gpriv["mod"]: return UserManagement.QUIZ_SERVER_MODERATOR
        
        return UserManagement.USER


    def get_all_members_userid(self, guild):
        guildid = guild
        if not isinstance(guild, str) and not isinstance(guild, int):
            guildid = guild.id
            
        all = set()
        g=self.get_members_guild(guildid)
        if g:
            for x in ["owner","admin","mod"]:
                all |= set(g[x])
        for x in ["owner","admin"]:
            all |= set(self.get_members_global()[x])
        return list(all)

    def get_members_global(self):
        return self.privs["global"]
    
    
    def get_members_guild(self, guild):
        guildid = guild
        if not isinstance(guild, str) and not isinstance(guild, int):
            guildid = guild.id
        
        guildid=int(guildid)
        
        if guildid not in self.privs["guilds"]:
            return None
        
        return self.privs["guilds"][guildid]
    
    @classmethod
    def lvl_to_string(cls, lvl):
        return UserManagement.DESC[lvl]
        

    @classmethod
    def string_to_lvl(cls, permission):
        perm = None
        if permission == "mod":
            perm=UserManagement.QUIZ_SERVER_MODERATOR
        if permission == "admin":
            perm=UserManagement.QUIZ_SERVER_ADMIN
        if permission == "owner":
            perm=UserManagement.QUIZ_SERVER_OWNER
        if permission == "bot_admin":
            perm=UserManagement.QUIZ_BOT_ADMIN
        if permission == "bot_owner":
            perm=UserManagement.QUIZ_BOT_OWNER
        if permission == "user":
            perm=UserManagement.USER
        return perm

 
 