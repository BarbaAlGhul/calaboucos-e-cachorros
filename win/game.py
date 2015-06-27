#!/usr/bin/python
# -*- coding: utf-8 -*-
###################################
#IMPORTANDO AS BIBLIOTECAS USADAS###
#####################################
#importando a biblioteca libtcodpy e renomeando para libtcod
import libtcodpy as libtcod
import math
import textwrap
import shelve

###################################
#DEFINIÇÃO DE TODAS AS CONSTANTES###
#####################################
#definindo o tamanho da tela e o fps do jogo
SCREEN_WIDTH = 80
SCREEN_HEIGHT = 50
LIMIT_FPS = 20

#definindo o tamanho do mapa(um pouco menor que o tamanho da tela para deixar espaço para o painel lateral)
MAP_WIDTH = 80
MAP_HEIGHT = 43

#definindo parâmetros para o gerador de dungeons
ROOM_MAX_SIZE = 10
ROOM_MIN_SIZE = 6
MAX_ROOMS = 30

#definindo o Field of View
FOV_ALGO = 0 #algoritmo padrão do FOV
FOV_LIGHT_WALLS = True
TORCH_RADIUS = 8

#definindo os tamanhos e coordenadas referentes ao GUI
BAR_WIDTH = 20
PANEL_HEIGHT = 7
PANEL_Y = SCREEN_HEIGHT - PANEL_HEIGHT

#definindo as constantes da barra de mensagem
MSG_X = BAR_WIDTH + 2
MSG_WIDTH = SCREEN_WIDTH - BAR_WIDTH - 2
MSG_HEIGHT = PANEL_HEIGHT - 1

#definindo a largura do menu
INVENTORY_WIDTH = 50

#definindo quantidade de HP que é recuperado por alguma ação ou item
HEAL_AMOUNT = 40

#definindo o dano e o alcance máximo da magia "relâmpago"
LIGHTNING_DAMAGE = 30
LIGHTNING_RANGE = 5

#definindo o alcance e o número máximo de turnos da magia "confusão"
CONFUSE_NUM_TURNS = 10
CONFUSE_RANGE = 8

#definindo o alcance e o dano da madia "bola de fogo"
FIREBALL_RADIUS = 3
FIREBALL_DAMAGE = 25

#definindo a experiência base e o fator para subir de nível
LEVEL_UP_BASE = 200
LEVEL_UP_FACTOR = 150

#definindo o tamanho da tela do console quando subir de nível
LEVEL_SCREEN_WIDTH = 40

#definindo o tamanho da tela do console das informações da personagem
CHARACTER_SCREEN_WIDTH = 30


#definindo as cores do mapa(paredes e chão)
color_dark_wall = libtcod.Color(51, 51, 51)
color_light_wall = libtcod.Color(119, 119, 119)
color_dark_ground = libtcod.Color(133, 94, 66)
color_light_ground = libtcod.Color(210, 180, 140)


###########################
#TODAS AS CLASSES DO JOGO###
#############################
class Tile:
	#um tile do mapa e suas propriedades
	def __init__(self, blocked, block_sight = None):
		self.blocked = blocked

		#todos os tiles começam inexplorados
		self.explored = False

		#por padrão, se um tile é bloqueado, ele também bloqueia a visão
		if block_sight is None: block_sight = blocked
		self.block_sight = block_sight


class Rect:
	#um retângulo no mapa, usado para criar salas.
	#pega as coordenadas do canto esquerdo superior e o tamanho.
	def __init__(self, x, y, w, h):
		self.x1 = x
		self.y1 = y
		self.x2 = x + w
		self.y2 = y + h

	#O método retorna as coordenadas do centro da sala, que é onde os túneis serão conectados
	def center(self):
		center_x = (self.x1 + self.x2) / 2
		center_y = (self.y1 + self.y2) / 2
		return (center_x, center_y)

	#O método verifica se existem intersecções, para evitar sobreposição de salas
	def intersect(self, other):
		#retorna verdadeiro se este retângulo intercepta outro retângulo
		return (self.x1 <= other.x2 and self.x2 >= other.x1 and
				self.y1 <= other.y2 and self.y2 >= other.y1)


class Object:
	#cria um objeto genérico: pode ser o jogadorm, um monstro, um item...
	#sempre será representado por um caractere na tela
	def __init__(self, x, y, char, name, color, blocks=False, always_visible=False, fighter=None, ai=None, item=None, equipment=None):
		self.always_visible = always_visible
		self.name = name
		self.blocks = blocks
		self.x = x
		self.y = y
		self.char = char
		self.color = color

		self.fighter = fighter
		if self.fighter: #o componente fighter fica sabendo a quem pertence
			self.fighter.owner = self

		self.ai = ai
		if self.ai: #o componente AI fica sabendo a quem pertence
			self.ai.owner = self

		self.item = item
		if self.item: #o componente item fica sabendo a quem pertence
			self.item.owner = self

		self.equipment = equipment
		if self.equipment: #deixa o compomente Equipment saber quem possui ele
			self.equipment.owner = self
			#deve existir um componente Item para o componente Equipment, para eles poderem funcionar corretamente, já que todo equipamento é um item
			self.item = Item()
			self.item.owner = self


	def move(self, dx, dy):
		#faz a movimentação pelo valor recebido se não estiver bloqueado
		if not is_blocked(self.x + dx, self.y + dy):
			self.x += dx
			self.y += dy

	def draw(self):
		#só exibe objetos dentro da FOV do jogador; ou se estiver "sempre visível" e em um tile explorado
		if (libtcod.map_is_in_fov(fov_map, self.x, self.y) or (self.always_visible and map[self.x][self.y].explored)):
			#define a cor e desenha o caracter que representa o objeto na sua posição
			libtcod.console_set_default_foreground(con, self.color)
			libtcod.console_put_char(con, self.x, self.y, self.char, libtcod.BKGND_NONE)

	def clear(self):
		#apaga o caracter que representa este objeto
		libtcod.console_put_char(con, self.x, self.y, ' ', libtcod.BKGND_NONE)
		#CASO ESTEJA USANDO CARACTERES OLD-SCHOOL PARA O CHÃO
		#if libtcod.map_is_in_fov(fov_map, self.x, self.y):
		#	libtcod.console_put_char_ex(con, self.x, self.y, '.', libtcod.white, libtcod.black)

	def move_towards(self, target_x, target_y):
		#vetor deste objeto ao alvo, e a distância
		dx = target_x - self.x
		dy = target_y - self.y
		distance = math.sqrt(dx ** 2 + dy ** 2)
		#normaliza o vetor para a distância 1 (preservando a direção), arredonda o resultado e converte
		#pra um número inteiro para o movimento ficar restrito ao grid do mapa
		dx = int(round(dx / distance))
		dy = int(round(dy / distance))
		self.move(dx, dy)

	def distance_to(self, other):
		#retorna a distância para outro objeto
		dx = other.x - self.x
		dy = other.y - self.y
		return math.sqrt(dx ** 2 + dy ** 2)

	def send_to_back(self):
		#faz esse objeto ser desenhado primeiro
		#então todos os outros objetos aparecerão em cima dele se estiverem no mesmo tile
		global objects
		objects.remove(self)
		objects.insert(0, self)

	def distance(self, x, y):
		#retorna a distância de algumas coordenadas
		return math.sqrt((x - self.x) ** 2 + (y - self.y) ** 2)


class Fighter:
	#nessa classe ficam todas as propriedades e métodos relacionados ao combate (monstros, jogador, NPCs)
	def __init__(self, hp, defense, power, xp, death_function = None):
		self.base_max_hp = hp
		self.hp = hp
		self.base_defense = defense
		self.base_power = power
		self.death_function = death_function
		self.xp = xp

	
	@property
	def power(self): #retorna o power atual somando com o valor do bonus de todos os equipamentos equipados
		bonus = sum(equipment.power_bonus for equipment in get_all_equipped(self.owner))
		return self.base_power + bonus

	@property
	def defense(self): #retorna o defense atual somando com o valor do bonus de todos os equipamentos equipados
		bonus = sum(equipment.defense_bonus for equipment in get_all_equipped(self.owner))
		return self.base_defense + bonus

	@property
	def max_hp(self): #retorna o max_hp atual somando com o valor do bonus de todos os equipamentos equipados
		bonus = sum(equipment.max_hp_bonus for equipment in get_all_equipped(self.owner))
		return self.base_max_hp + bonus
		

	def take_damage(self, damage):
		#aplica o dano se possível
		if damage > 0:
			self.hp -= damage

		#verifica se está morto (HP <= 0). Chama a função de morte
		if self.hp <= 0:
			function = self.death_function
			if function is not None:
				function(self.owner)
			if self.owner != player: #adiciona experiência ao jogador
				player.fighter.xp += self.xp

	def attack(self, target):
		#fórmula simples para cálcular o ataque
		damage = self.power - target.fighter.defense

		if damage > 0:
			#faz o alvo tomar dano
			message(self.owner.name.capitalize() + ' ataca o ' + target.name + ' e causa ' + str(damage) + ' pontos de dano.')
			target.fighter.take_damage(damage)
		else:
			message(self.owner.name.capitalize() + ' ataca o ' + target.name + ' mas nao tem efeito!')

	def heal(self, amount):
		#cura segundo o valor dado, sem ultrapassar o limite máximo
		self.hp += amount
		if self.hp > self.max_hp:
			self.hp = self.max_hp


class BasicMonster:
	#AI básica para um monstro
	def take_turn(self):
		#um monstro básico faz o seu turno. Se o jogador pode vê-lo, o monstro pode ver você
		monster = self.owner
		if libtcod.map_is_in_fov(fov_map, monster.x, monster.y):
			#se move em direção ao jogador se estiver longe
			if monster.distance_to(player) >= 2:
				monster.move_towards(player.x, player.y)

			#está perto o suficiente, ataca! (se o jogador ainda estiver vivo)
			elif player.fighter.hp > 0:
				monster.fighter.attack(player)


class ConfusedMonster:
	#AI para um monstro atordoado
	def __init__(self, old_ai, num_turns=CONFUSE_NUM_TURNS):
		#verifica o número de turnos que o monstro ficará atordoado e depois restaura a AI antiga
		self.old_ai = old_ai
		self.num_turns = num_turns

	def take_turn(self):
		if self.num_turns > 0: #ainda está confuso
			#faz um movimento em uma direção aleatória
			self.owner.move(libtcod.random_get_int(0, -1, 1), libtcod.random_get_int(0, -1, 1))
			self.num_turns -= 1

		else: #restaura a AI anterior, deletando a AI atual
			self.owner.ai = self.old_ai
			message('O ' + self.owner.name + ' nao esta mais confuso!', libtcod.desaturated_red)


class Item:
	def __init__(self, use_function=None):
		self.use_function = use_function
	#um item que pode ser pegado e usado
	def pick_up(self):
		#adiciona ao inventário do jogador e remove o item do mapa
		if len(inventory) >=26:
			message('Seu inventario esta cheio, voce nao pode pegar o item ' + self.owner.name + '.', libtcod.red)
		else:
			inventory.append(self.owner)
			objects.remove(self.owner)
			if self.owner.name[0:6] == 'pocao':
				message('Voce pegou uma ' + self.owner.name + '!', libtcod.green)
			else:
				message('Voce pegou um ' + self.owner.name + '!', libtcod.green)

	def use(self):
		#caso especial: se o objeto contem o componente Equipment, a ação de usar equipa ou desequipa o item
		if self.owner.equipment:
			self.owner.equipment.toggle_equip()
			return

		#chama a "use_function" se ela está definida
		if self.use_function is None:
			message('O item ' + self.owner.name + ' nao pode ser usado')
		else:
			if self.use_function() != 'cancelled':
				inventory.remove(self.owner) #destrói o item após o uso, a menos que seja cancelada a ação

	def drop(self):
		#adiciona ao mapa e remove do inventário do jogador. E adiciona o item nas coordenadas do jogador
		objects.append(self.owner)
		inventory.remove(self.owner)
		self.owner.x = player.x
		self.owner.y = player.y
		if self.owner.name[0:6] == 'pocao' or self.owner.name[:-1] == 'a':
			message('Voce largou uma ' + self.owner.name + '.', libtcod.yellow)
		else:
			message('Voce largou um ' + self.owner.name + '.', libtcod.yellow)
		
		#caso especial: se o objeto for um equipamento, desequipa ele antes de jogar fora
		if self.owner.equipment:
			self.owner.equipment.dequip()


class Equipment:
	#um objeto que pode ser equipado, rendendo bonus. Adiciona o componente Item automaticamente.
	def __init__(self, slot, power_bonus=0, defense_bonus=0, max_hp_bonus=0):
		self.power_bonus = power_bonus
		self.defense_bonus = defense_bonus
		self.max_hp_bonus = max_hp_bonus
		self.slot = slot
		self.is_equipped = False
		

	def toggle_equip(self): #muda o status de equipado para não equipado
		if self.is_equipped:
			self.dequip()
		else:
			self.equip()

	def equip(self):
		#se o slot já estiver sendo usado, desequipa o que estiver lá no momento
		old_equipment = get_equipped_in_slot(self.slot)
		if old_equipment is not None:
			old_equipment.dequip()
			#caso especial: automaticamente equipa um item se o slot correspondente estiver vazio
			#equipment = self.owner.equipment
			#if equipment and get_equipped_in_slot(equipment.slot) is None:
			#	equipment.equip()

		#equipa um objeto e mostra uma mensagem sobre isso
		self.is_equipped = True
		message('Equipou ' + self.owner.name + ' na ' + self.slot + '.', libtcod.light_green)

	def dequip(self):
		#desequipa o objeto e mostra uma mensagem sobre isso
		if not self.is_equipped: return
		self.is_equipped = False
		message('Retirou ' + self.owner.name + 'da' + self.slot + '.', libtcod.light_yellow)



####################################################################
#FUNÇÃO PARA VERIFICAR SE UM ÍTEM EQUIPADO ESTÁ EM MAIS DE UM SLOT###
######################################################################
def get_equipped_in_slot(slot): #retorna o equipamento em um slot ou None se estiver vazio
	for obj in inventory:
		if obj.equipment and obj.equipment.slot == slot and obj.equipment.is_equipped:
			return obj.equipment
	return None


##################################################
#FUNÇÃO PARA RETORNAR A LISTA DE ITEMS EQUIPADOS###
####################################################
def get_all_equipped(obj): #retorna uma lista de itens equipados
	if obj == player:
		equipped_list = []
		for item in inventory:
			if item.equipment and item.equipment.is_equipped:
				equipped_list.append(item.equipment)
		return equipped_list
	else:
		return [] #os outros objetos não tem nenhum equipamento


#############################################
#FUNÇÃO QUE TESTA SE UM TILE ESTÁ BLOQUEADO###
###############################################
def is_blocked(x, y):
	#primeiro testa o tile do mapa
	if map[x][y].blocked:
		return True

	#verifica para qualquer outro objeto
	for object in objects:
		if object.blocks and object.x == x and object.y == y:
			return True

	return False


#############################
#FUNÇÃO PARA CRIAR UMA SALA###
###############################
def creat_room(room):
	global map
	#percorre os tiles no retângulo e torna eles passáveis
	for x in range(room.x1 + 1, room.x2):
		for y in range(room.y1 + 1, room.y2):
			map[x][y].blocked = False
			map[x][y].block_sight = False


########################################
#FUNÇÃO PARA CRIAR UM TÚNEL HORIZONTAL###
##########################################
def create_h_tunnel(x1, x2, y):
	global map
	for x in range(min(x1, x2), max(x1, x2) + 1):
		map[x][y].blocked = False
		map[x][y].block_sight = False


######################################
#FUNÇÃO PARA CRIAR UM TÚNEL VERTICAL###
########################################
def create_v_tunnel(y1, y2, x):
	global map
	#túnel vertical
	for y in range(min(y1, y2), max(y1, y2) + 1):
		map[x][y].blocked = False
		map[x][y].block_sight = False


#############################
#FUNÇÃO PARA CRIAR O MAPA#####
###############################
def make_map():
	global map, objects, stairs

	#cria uma lista com os objetos
	objects = [player]

	#preenche o mapa com tiles "bloqueados"
	map = [[ Tile(True)
		for y in range(MAP_HEIGHT) ]
			for x in range(MAP_WIDTH) ]

	rooms = []
	num_rooms = 0

	for r in range(MAX_ROOMS):
		#altura e largura aleatórios
		w = libtcod.random_get_int(0, ROOM_MIN_SIZE, ROOM_MAX_SIZE)
		h = libtcod.random_get_int(0, ROOM_MIN_SIZE, ROOM_MAX_SIZE)
		#posição aleatória dentro dos limites do mapa
		x = libtcod.random_get_int(0, 0, MAP_WIDTH - w - 1)
		y = libtcod.random_get_int(0, 0, MAP_HEIGHT -h - 1)

		#Classe "Rect" faz com que seja mais fácil lidar com retângulos
		new_room = Rect(x, y, w, h)

		#percorre as outras salas e verifica se elas interceptam com esta
		failed = False
		for other_room in rooms:
			if new_room.intersect(other_room):
				failed = True
				break

		#se a sala for válida, então ela é criada. O jogador começa no centro da primeira sala
		if not failed:
			#isto significa que não existem intersecções, então a sala é válida
			#"desenha" a sala nos tiles do mapa
			creat_room(new_room)

			#adiciona conteúdo à sala, como monstros por exemplo
			place_objects(new_room)

			#coordenadas centrais da nova sala
			(new_x, new_y) = new_room.center()

			if num_rooms == 0:
				#esta é a primeira sala, onde o jogador começa
				player.x = new_x
				player.y = new_y
			else:
				#todas as outras salas após a primeira
				#conecta a próxima sala com a sala anterior através de um túnel

				#coordenadas centrais da sala anterior
				(prev_x, prev_y) = rooms[num_rooms-1].center()

				#sorteia um número (número aleatório que é 0 ou 1)
				if libtcod.random_get_int(0, 0, 1) == 1:
					#primeiro move horizontalmente, depois verticalmente
					create_h_tunnel(prev_x, new_x, prev_y)
					create_v_tunnel(prev_y, new_y, new_x)
				else:
					#primeiro move verticalmente, depois horizontalmente
					create_v_tunnel(prev_y, new_y, prev_x)
					create_h_tunnel(prev_x, new_x, new_y)

			#finalmente, anexa a nova sala à lista
			rooms.append(new_room)
			num_rooms += 1

	#cria escadas no centro da última sala
	stairs = Object(new_x, new_y, '<', 'escadas', libtcod.white, always_visible = True)
	objects.append(stairs)
	stairs.send_to_back() #será impressa na tela atrás dos monstros


################################
#FUNÇÃO DE ESCOLHAS ALEATÓRIAS###
##################################
def random_choice_index(chances):#escolhe uma opção de uma lista de chances e retorna o índice da chance
  #o dado vai cair em um número entre 1 e a soma das chances
  dice = libtcod.random_get_int(0, 1, sum(chances))

  #percorre todas as chances, mantendo a soma
  running_sum = 0
  choice = 0
  for w in chances:
  	running_sum += w

  	#verifica se o dado caiu com o lado que corresponde à sua escolha
  	if dice <= running_sum:
  		return choice
  	choice += 1


##################################################
#FUNÇÃO DE ESCOLHAS ALEATÓRIAS(PARA DICIONÁRIOS)###
####################################################
def random_choice(chances_dict):
	#escolhe uma opção de um dicionário de chances, retornando a chave
	chances = chances_dict.values()
	strings = chances_dict.keys()

	return strings[random_choice_index(chances)]


##############################################
#FUNÇÃO PARA TABELA DE PROGRESSÃO DOS NÍVEIS###
################################################
def from_dungeon_level(table):
	#retorna um valor que depende do nível. A tabela especifica qual valor que ocorre após cada nível, o padrão é 0
	for (value, level) in reversed(table):
		if dungeon_level >= level:
			return value
	return 0


######################################################
#FUNÇÃO PARA POPULAR UMA SALA (ITENS, MONSTROS, ETC)###
########################################################
#aqui é onde é decidido a chance de cada monstro ou item aparecer
def place_objects(room):
	#número máximo de monstros por sala
	max_monsters = from_dungeon_level([[2,1], [3,4], [5,6]])

	#chance de cada monstro
	monster_chances = {}
	monster_chances['rato'] = 80 #o rato sempre é criado, mesmo se todos os outros monstros tiverem chance 0
	monster_chances['troll'] = from_dungeon_level([[15,3], [30, 5], [60, 7]])
	monster_chances['kobold'] = from_dungeon_level([[25,2], [45, 4], [75, 8]])
	monster_chances['orc'] = from_dungeon_level([[35,2], [45, 3], [80, 6]])

	#máximo de items por sala
	max_items = from_dungeon_level([[1,1],[2,4]])

	#chance de cada item(por padrão eles tem chance 0 no level 1)
	item_chances = {}
	item_chances['cura'] = 35 #poções de cura sempre aparecem mesmo se a chance dos outros itens for 0
	item_chances['relampago'] = from_dungeon_level([[25, 4]])
	item_chances['bola de fogo'] =  from_dungeon_level([[25, 6]])
	item_chances['confusao'] =   from_dungeon_level([[10, 2]])
	item_chances['espada'] = from_dungeon_level([[5,4]])
	item_chances['escudo'] = from_dungeon_level([[15,8]])

	#escolhe um numero aleatório de monstros
	num_monsters = libtcod.random_get_int(0, 0, max_monsters)

	for i in range(num_monsters):
		#escolhe um ponto aleatório para o monstro
		x = libtcod.random_get_int(0, room.x1+1, room.x2-1)
		y = libtcod.random_get_int(0, room.y1+1, room.y2-1)
		#chances de criar os monstros: 20% Troll, 40% Rato, 10% Kobold, 30% Orc:
		choice = libtcod.random_get_int(0, 0, 100)
		#só coloca o monstro se o tile não estiver bloqueado
		if not is_blocked(x, y):
			choice = random_choice(monster_chances)
			if  choice == 'kobold':
					#cria um Kobold
					fighter_component = Fighter(hp=16, defense=1, power=3, xp=30, death_function = monster_death)
					ai_component = BasicMonster()
					monster = Object(x, y, 'k', 'kobold', libtcod.desaturated_red, blocks=True, fighter = fighter_component, ai = ai_component)
			elif choice == 'rato':
					#cria um Rato
					fighter_component = Fighter(hp=12, defense=0, power=2, xp=10, death_function = monster_death)
					ai_component = BasicMonster()
					monster = Object(x, y, 'r', 'rato', libtcod.darkest_orange, blocks=True, fighter = fighter_component, ai = ai_component)
			elif choice == 'troll':
					#cria um Troll
					fighter_component = Fighter(hp=32, defense=2, power=8, xp =80, death_function = monster_death)
					ai_component = BasicMonster()
					monster = Object(x, y, 'T', 'troll', libtcod.darker_green, blocks=True, fighter = fighter_component, ai = ai_component)
			elif choice == 'orc':
					#cria um Orc
					fighter_component = Fighter(hp=20, defense=1, power=4, xp=40, death_function = monster_death)
					ai_component = BasicMonster()
					monster = Object(x, y, 'o', 'orc', libtcod.desaturated_green, blocks=True, fighter = fighter_component, ai = ai_component)

			objects.append(monster)

	#escolhe um número aleatório de ítens
	num_items = libtcod.random_get_int(0, 0, max_items)

	for i in range(num_items):
		#escolhe um lugar aleatório para o item
		x = libtcod.random_get_int(0, room.x1+1, room.x2-1)
		y = libtcod.random_get_int(0, room.y1+1, room.y2-1)

		#só coloca o item se o tile não estiver bloqueado
		if not is_blocked(x, y):
			choice = random_choice(item_chances)
			if choice == 'cura':
				#cria uma poção de cura
				item_component = Item(use_function=cast_heal)
				item = Object(x, y, '!', 'pocao de cura', libtcod.violet, item=item_component)
			elif choice == 'relampago':
				#cria um pergaminho com a magia "relâmpago"
				item_component = Item(use_function=cast_lightning)
				item = Object(x, y, '#', 'pergaminho relampago', libtcod.light_yellow, item=item_component)
			elif choice == 'bola de fogo':
				#cria um pergaminho com a magia "bola de fogo"
				item_component = Item(use_function=cast_fireball)
				item = Object(x, y, '#', 'pergaminho bola de fogo', libtcod.light_yellow, item=item_component)
			elif choice == 'confusao':
				#cria um pergaminho com a magia "confusão"
				item_component = Item(use_function=cast_confuse)
				item = Object(x, y, '#', 'pergaminho confusao', libtcod.light_yellow, item=item_component)
			elif choice == 'espada':
				#cria uma espada simples
				equipment_component = Equipment(slot = 'mao direita', power_bonus=3)
				item = Object(x, y, '/', 'espada', libtcod.sky, equipment = equipment_component)
			elif choice == 'escudo':
				equipment_component = Equipment(slot='mao esquerda', defense_bonus=1)
				item = Object(x, y, '[', 'escudo', libtcod.darker_orange, equipment = equipment_component)


			objects.append(item)
			item.send_to_back() #o item aparece atrás dos outros objetos
			item.always_visible = True #items sempre ficam visíveis se estiverem em uma área previamente explorada



###########################################################
#FUNÇÃO PARA VERIFICAR SE O JOGADOR SE MOVIMENTA OU ATACA###
#############################################################
def player_move_or_attack(dx, dy):
	global fov_recompute

	#as coordenadas que o jogador está se movendo/atacando
	x = player.x + dx
	y = player.y + dy

	#tenta encontrar um objeto que seja possível atacar
	target = None
	for object in objects:
		if object.fighter and object.x == x and object.y == y:
			target = object
			break

	#ataca se um alvo for encontrado, caso contrário faz a movimentação
	if target is not None:
		player.fighter.attack(target)
	else:
		player.move(dx, dy)
		fov_recompute = True


###########################################
#FUNÇÃO PARA VERIFICAR A MORTE DO JOGADOR###
#############################################
def player_death(player):
	#termina o jogo!
	global game_state
	message('Voce morreu!', libtcod.red)
	game_state = 'dead'

	#Transforma o corpo do jogador morto
	player.char = '%'
	player.color = libtcod.dark_red


###########################################
#FUNÇÃO PARA VERIFICAR A MORTE DO MONSTRO###
#############################################
def monster_death(monster):
	#transforma o monstro em um corpo morto que não pode se mover, não pode ser atacado e nem bloqueia o caminho
	message(monster.name.capitalize() + ' esta morto! Voce ganhou ' + str(monster.fighter.xp) + ' pontos de experiencia', libtcod.orange)
	monster.char = '%'
	monster.color = libtcod.dark_red
	monster.blocks = False
	monster.fighter = None
	monster.ai = None
	monster.name = 'restos de um ' + monster.name
	monster.send_to_back()


####################################
#FUNÇÃO PARA CRIAR O PAINEL DA GUI###
######################################
def render_bar(x, y, total_width, name, value, maximum, bar_color, back_color):
	#renderiza uma barra (HP, XP, etc). Primeiro calcula a largura da barra
	bar_width = int(float(value) / maximum * total_width)

	#renderiza primeiro o background
	libtcod.console_set_default_background(panel, back_color)
	libtcod.console_rect(panel, x, y, total_width, 1, False, libtcod.BKGND_SCREEN)

	#renderiza a barra do topo
	libtcod.console_set_default_background(panel, bar_color)
	if bar_width > 0:
		libtcod.console_rect(panel, x, y, bar_width, 1, False, libtcod.BKGND_SCREEN)

	#texto centralizado com os valores
	libtcod.console_set_default_foreground(panel, libtcod.white)
	libtcod.console_print_ex(panel, x + total_width / 2, y, libtcod.BKGND_NONE, libtcod.CENTER,
		name + ': ' + str(value) + '/' + str(maximum))


###########################################
#FUNÇÃO PARA ADICIONAR MENSAGENS NA LISTA###
#############################################
def message(new_msg, color = libtcod.white):
	#se necessário, divide a mensagem em múltiplas linhas
	new_msg_lines = textwrap.wrap(new_msg, MSG_WIDTH)

	for line in new_msg_lines:
		#se o buffer estiver cheio, remove a primeira linha para dar espaço para uma nova linha
		if len(game_msgs) == MSG_HEIGHT:
			del game_msgs[0]

		#adiciona uma nova linha como uma tupla, com texto e a cor
		game_msgs.append( (line, color))


#############################################################
#FUNÇÃO PARA IMPRIMIR NOMES DE OBJETOS APONTADOS PELO MOUSE###
###############################################################
def get_names_under_mouse():
	global mouse
	#retorna uma string com os nomes de todos os objetos apontados pelo mouse
	(x, y) = (mouse.cx, mouse.cy)
	#cria uma lista com os nomes de todos os objetos apontados pelo mouse e dentro do FOV
	names = [obj.name for obj in objects
	if obj.x == x and obj.y == y and libtcod.map_is_in_fov(fov_map, obj.x, obj.y)]
	#junta todos os nomes na mesma string, separados por vírgula
	names = ', '.join(names)
	return names.capitalize()


##############
#FUNÇÃO MENU###
################
def menu(header, options, width):
	#verifica se não há mais opções do que o permitido (26 opções, o número de letras do alfabeto)
	if len(options) > 26: raise ValueError('Nao pode haver um menu com mais de 26 opcoes.')
	#calculando a altura do header do menu e adicionando uma linha por opção
	header_height = libtcod.console_get_height_rect(con, 0, 0, width, SCREEN_HEIGHT, header)
	if header == '' :#tira a linha em branco do menu principal
		header_height = 0
	height = len(options) + header_height

	#cria um console "off-screen" que representa a janela do menu
	window = libtcod.console_new(width, height)

	#imprime o header, com o auto-wrap
	libtcod.console_set_default_foreground(window, libtcod.white)
	libtcod.console_print_rect_ex(window, 0, 0, width, height, libtcod.BKGND_NONE, libtcod.LEFT, header)

	#imprime todas as opções, incrementando o loop a partir da letra 'a'
	y = header_height
	letter_index = ord('a') #pega o código ASCII da letra 'a'
	for option_text in options:
		text = '(' + chr(letter_index) + ')' + option_text #chr converte de volta o código ASCII para um caractere
		libtcod.console_print_ex(window, 0, y, libtcod.BKGND_NONE, libtcod.LEFT, text)
		y +=1
		letter_index +=1

	#chama o console off-screen para imprimir na tela
	#calcula a posição do canto esquerdo superior da tela, para o console ficar centralizado
	x = SCREEN_WIDTH/2 - width/2
	y = SCREEN_HEIGHT/2 - height/2
	libtcod.console_blit(window, 0, 0, width, height, 0, x, y, 1.0, 0.7) #os últimos dois parâmetros definem a transparência do foreground e do background

	#mostra o root console ao jogador e espera uma tecla ser pressionada
	libtcod.console_flush()
	key = libtcod.console_wait_for_keypress(True)
	if key.vk == libtcod.KEY_F12: #F12 entra em fullscreen no menu principal
		libtcod.console_set_fullscreen(not libtcod.console_is_fullscreen())

	#converte o código ASCII em um índice; se corresponder a uma opção, retorna ela
	index = key.c - ord('a')
	if index >= 0 and index < len(options): return index
	return None


###################################
#FUNÇÃO QUE MOSTRA O MENU NA TELA###
#####################################
def inventory_menu(header):
	#mostra o menu com cada item do inventário como uma opção
	if len(inventory) == 0:
		options = ['O inventario esta vazio']
	else:
		options = []
		for item in inventory:
			text = item.name
			#mostra informações adicionais, no caso se está equiapdo
			if item.equipment and item.equipment.is_equipped:
				text = text + ' (na ' + item.equipment.slot + ')'
			options.append(text)

	index = menu(header, options, INVENTORY_WIDTH)

	#se um item foi escolhido, retorna ele
	if index is None or len(inventory) == 0: return None
	return inventory[index].item




######################
#FUNÇÃO CURA JOGADOR###
########################
def cast_heal():
	#cura o jogador
	if player.fighter.hp == player.fighter.max_hp:
		message('Voce ja esta com a vida cheia.', libtcod.red)
		return 'cancelled'

	message('Suas feridas comecam a ficar melhores!', libtcod.light_violet)
	player.fighter.heal(HEAL_AMOUNT)


#########################
#FUNÇÃO MAGIA RELÂMPAGO###
###########################
def cast_lightning():
	#procura pelo inimigo mais próximo (dentro do alcance máximo) e da o dano
	monster = closest_monster(LIGHTNING_RANGE)
	if monster is None: #nenhum inimigo é encontrado dentro do alcance
		message('Nenhum inimigo esta proximo o suficiente para sofrer o dano')
		return 'cancelled'
	#inflige o dano
	message('Um relampago acerta o ' + monster.name + ' com um forte trovao! O dano e de '
		+ str(LIGHTNING_DAMAGE) + ' pontos', libtcod.light_blue)
	monster.fighter.take_damage(LIGHTNING_DAMAGE)


########################
#FUNÇÃO MAGIA CONFUSÃO###
##########################
def cast_confuse():
	#pergunta ao jogador para selecionar um alvo para a magia
	message('Clique com o botao esquerdo em um inimigo para deixa-lo confuso, ou clique com o botao direito para cancelar.', libtcod.light_cyan)
	monster = target_monster(CONFUSE_RANGE)
	if monster is None: #nenhum inimigo é selecionado
		return 'cancelled'
	
	#troca a AI do monstro pela a AI da magia confusão. Após alguns turnos, a AI antiga será restaurada
	old_ai = monster.ai
	monster.ai = ConfusedMonster(old_ai)
	monster.ai.owner = monster #define quem é o alvo da nova AI
	message('Os olhos do ' + monster.name + ' parecem vagos, logo ele comeca a tropecar por ai', libtcod.light_green)


############################
#FUNÇÃO MAGIA BOLA DE FOGO###
##############################
def cast_fireball():
	#pede ao jogador um alvo para a bola de fogo
	message('Clique com o botao esquerdo em um tile alvo, ou clique com o botao direito para cancelar.', libtcod.light_cyan)
	(x, y) = target_tile()
	if x is None: return 'canclled'
	message('A bola de fogo explode, queimando tudo dentro de ' + str(FIREBALL_RADIUS) + ' tiles!', libtcod.orange)

	for obj in objects: #causa dano em todos no alcance, inclusive o jogador
		if obj.distance(x, y) <= FIREBALL_RADIUS and obj.fighter: #para deixar o jogador imune, basta adicionar 'and obj!=player' no if
			message('O ' + obj.name + ' foi queimado e sofreu ' + str(FIREBALL_DAMAGE) + ' de dano', libtcod.orange)
			obj.fighter.take_damage(FIREBALL_DAMAGE)


###############################################
#FUNÇÃO PARA VERIFICAR O MONSTRO MAIS PRÓXIMO###
#################################################
def closest_monster(max_range):
	#procura o inimigo mais perto, no limite do alcance máximo, dentro do FOV do jogador
	closest_enemy = None
	closest_dist = max_range + 1 #começa com o alcance um pouco maior que o inicial

	for object in objects:
		if object.fighter and not object == player and libtcod.map_is_in_fov(fov_map, object.x, object.y):
			#calcula a distância entre este objeto e o jogador
			dist = player.distance_to(object)
			if dist < closest_dist: #está perto
				closest_enemy = object
				closest_dist = dist
	return closest_enemy



###########################################################
#FUNÇÃO PARA VERIFICAR UM TILE ALVO COM O CLIQUE DO MOUSE###
#############################################################
def target_tile(max_range=None):
	#retorna a posição de um tile que foi clicado com o botão esquerdo do mouse dentro da FOV do jogador,
	#(opcionalmente dentro de um alcance), ou (None, None) se clicado com o botão direito.
	global key, mouse
	while True:
		#renderiza a tela. Isso apaga o inventário e mostra o nome dos objetos apontados pelo mouse
		libtcod.console_flush()
		libtcod.sys_check_for_event(libtcod.EVENT_KEY_PRESS|libtcod.EVENT_MOUSE, key, mouse)
		render_all()

		(x, y) = (mouse.cx, mouse.cy)
		#aceita o alvo se o jogador clicou dentro do FOV e, em case de um alcance for especificado, aceita se está dentro do alcance
		if (mouse.lbutton_pressed and libtcod.map_is_in_fov(fov_map, x, y) and (max_range is None or player.distance(x, y) <= max_range)):
			return (x, y)
		if mouse.rbutton_pressed or key.vk == libtcod.KEY_ESCAPE: #cancela se o jogador apertar ESC ou o botão direito do mouse
			return (None, None)


##############################################################
#FUNÇÃO PARA VERIFICAR UM MONSTRO ALVO COM O CLIQUE DO MOUSE###
################################################################
def target_monster(max_range=None):
	#retorna um monstro clicado dentro do FOV dentro de um alcance, ou None se for clicado com o botão direito
	while True:
		(x, y) = target_tile(max_range)
		if x is None: #o jogador cancelou a ação
			return None

		#retorna o primeiro monstro clicado, caso contrário continua o loop
		for obj in objects:
			if obj.x == x and obj.y == y and obj.fighter and obj != player:
				return obj


#######################################################
#FUNÇÃO PARA VERIFICAR SE O NÍVEL DA PERSONAGEM SUBIU###
#########################################################
def check_level_up():
	#verifica se a experiência do jogador é suficiente para subir de nível
	level_up_xp = LEVEL_UP_BASE + player.level * LEVEL_UP_FACTOR
	if player.fighter.xp >= level_up_xp:
		#tem experiência suficiente, sobe de nível
		player.level += 1
		player.fighter.xp -= level_up_xp
		message('Suas habilidades de combate ficaram mais fortes! Voce subiu para o nivel ' + str(player.level) + '!', libtcod.yellow)

		#após o jogador subir de nível, o jogador escolhe quais atributos ele quer melhorar
		choice = None
		while choice == None: #continua perguntando até o jogador responder
			choice = menu('Subiu de nivel! Escolha um atributo para melhorar:\n',
				['Constituicao (+20 HP, de ' + str(player.fighter.max_hp) + ')',
				'Forca (+1 ataque, de ' + str(player.fighter.power) + ')',
				'Agilidade (+1 defesa, de ' + str(player.fighter.defense) + ')'], LEVEL_SCREEN_WIDTH)

		if choice == 0:
			player.fighter.base_max_hp += 20
			player.fighter.hp += 20
		elif choice == 1:
			player.fighter.base_power += 1
		elif choice == 2:
			player.fighter.base_defense += 1


###################################################
#FUNÇÃO PARA DESENHAR O MAPA E OS OBJETOS NA TELA###
#####################################################
def render_all():
	global fov_map, color_dark_wall, color_light_wall
	global color_dark_ground, color_light_ground
	global fov_recompute

	if fov_recompute:
		#recomputa o FOV se necessário (caso o jogador se mova por exemplo)
		fov_recompute = False
		libtcod.map_compute_fov(fov_map, player.x, player.y, TORCH_RADIUS, FOV_LIGHT_WALLS, FOV_ALGO)

		#percorre todos os tiles e coloca a cor de fundo de acordo com o FOV
		for y in range(MAP_HEIGHT):
			for x in range(MAP_WIDTH):
				visible = libtcod.map_is_in_fov(fov_map, x, y)
				wall = map[x][y].block_sight
				if not visible:
					#se não estiver visível agora, o jogador só pode ver se já foi explorado
					if map[x][y].explored:
						# se estiver fora da FOV do jogador
						if wall:
							#Essa linha cria uma parede com os gráficos da biblioteca
							libtcod.console_set_char_background(con, x, y, color_dark_wall, libtcod.BKGND_SET)
							#Essa linha cria uma parede com gráficos old-school
							#libtcod.console_put_char_ex(con,x ,y, '#', libtcod.white, libtcod.black)
						else:
							#Essa linha cria o chão com os gráficos da biblioteca
							libtcod.console_set_char_background(con, x, y, color_dark_ground, libtcod.BKGND_SET)
							#Essa linha cria o chão com gráficos old-school
							#libtcod.console_put_char_ex(con,x ,y, '.', libtcod.white, libtcod.black)
				else:
					#se for visível
					if wall:
						#Essa linha cria uma parede com os gráficos da biblioteca
						libtcod.console_set_char_background(con, x, y, color_light_wall, libtcod.BKGND_SET)
						#Essa linha cria uma parede com gráficos old-school
						#libtcod.console_put_char_ex(con,x ,y, '#', libtcod.white, libtcod.black)
					else:
						#Essa linha cria o chão com os gráficos da biblioteca
						libtcod.console_set_char_background(con, x, y, color_light_ground, libtcod.BKGND_SET)
						#Essa linha cria o chão com gráficos old-school
						#libtcod.console_put_char_ex(con,x ,y, '.', libtcod.white, libtcod.black)

					#já que é visível, pode ser explorado
					map[x][y].explored = True
	
	#desenha todos os objetos da lista, exceto o jogador.
	#o jogador deve aparecer por cima de todos os outros objetos, então ele será desenhado depois
	for object in objects:
		if object != player:
			object.draw()
	player.draw()

	#a função console_blit cria uma nova área do mesmo tamanho da tela para o novo console
	libtcod.console_blit(con, 0, 0, MAP_WIDTH, MAP_HEIGHT, 0, 0, 0)

	#prepara para renderizar o painel GUI
	libtcod.console_set_default_background(panel, libtcod.black)
	libtcod.console_clear(panel)

	#imprime as mensagens do jogo, uma por vez
	y = 1
	for (line, color) in game_msgs:
		libtcod.console_set_default_foreground(panel, color)
		libtcod.console_print_ex(panel, MSG_X, y, libtcod.BKGND_NONE, libtcod.LEFT, line)
		y += 1

	#mostra a barra de status do jogador
	render_bar(1, 1, BAR_WIDTH, 'HP', player.fighter.hp, player.fighter.max_hp,
		libtcod.light_red, libtcod.darker_red)

	#texto para informar sobre o nível da dungeon
	libtcod.console_print_ex(panel, 1, 3, libtcod.BKGND_NONE, libtcod.LEFT, 'Calabouco nivel ' + str(dungeon_level))

	#mostra os nomes dos objetos apontados pelo mouse
	libtcod.console_set_default_foreground(panel, libtcod.light_gray)
	libtcod.console_print_ex(panel, 1, 0, libtcod.BKGND_NONE, libtcod.LEFT, get_names_under_mouse())

	#liga o conteúdo do painel ao root console
	libtcod.console_blit(panel, 0, 0, SCREEN_WIDTH, PANEL_HEIGHT, 0, 0, PANEL_Y)


#############################
#FUNÇÃO PARA A MOVIMENTAÇÃO###
###############################
def handle_keys():
	global key
	#Entra no modo tela cheia, primeiro verifica por eventos do mouse ou do teclado
	libtcod.sys_check_for_event(libtcod.EVENT_KEY_PRESS|libtcod.EVENT_MOUSE,key,mouse)
	#F12 entra em tela cheia
	if key.vk == libtcod.KEY_F12:
		libtcod.console_set_fullscreen(not libtcod.console_is_fullscreen())

	#Esc sai do jogo
	if key.vk == libtcod.KEY_ESCAPE:
		return 'exit' #sai do jogo

	#teclas de movimentação e combate só podem ser usadas se o status do jogo é "playing"
	if game_state == 'playing':
		#teclas de movimentação
		if key.vk == libtcod.KEY_UP or key.vk == libtcod.KEY_KP8:
			player_move_or_attack(0, -1)

		elif key.vk == libtcod.KEY_DOWN or key.vk == libtcod.KEY_KP2:
			player_move_or_attack(0, 1)

		elif key.vk == libtcod.KEY_LEFT or key.vk == libtcod.KEY_KP4:
			player_move_or_attack(-1, 0)

		elif key.vk == libtcod.KEY_RIGHT or key.vk == libtcod.KEY_KP6:
			player_move_or_attack(1, 0)
		
		elif key.vk == libtcod.KEY_HOME or key.vk == libtcod.KEY_KP7:
			player_move_or_attack(-1, -1)
		
		elif key.vk == libtcod.KEY_PAGEUP or key.vk == libtcod.KEY_KP9:
			player_move_or_attack(1, -1)

		elif key.vk == libtcod.KEY_END or key.vk == libtcod.KEY_KP1:
			player_move_or_attack(-1, 1)

		elif key.vk == libtcod.KEY_PAGEDOWN or key.vk == libtcod.KEY_KP3:
			player_move_or_attack(1, 1)

		elif key.vk == libtcod.KEY_KP5 or key.vk == libtcod.KEY_ENTER:
			pass #não faz nada, espera o turno dos monstros (espera os monstros chegarem mais perto se eles estiverem no campo de visão)

		else:
			#testa outras teclas
			key_char = chr(key.c)
			#a tecla g pega um item
			if key_char == 'g':
				#pega um item
				for object in objects: #procura por um item no tile do jogador
					if object.x == player.x and object.y == player.y and object.item:
						object.item.pick_up()
						break
			#a tecla i mostra o inventário
			if key_char == 'i':
				#mostra o inventário; se um item for selecionado, usa ele
				chosen_item = inventory_menu('Aperte uma tecla proxima a um item para usa-lo ou qualquer outra para cancelar.\n')
				if chosen_item is not None:
					chosen_item.use()
			#a tecla d larga um item do inventário
			if key_char == 'd':
				#mostra o inventário e se um item for selecionado, larga ele
				chosen_item = inventory_menu('Aperte a tecla proxima a um item para larga-lo, ou qualquer outra para cancelar.\n')
				if chosen_item is not None:
					chosen_item.drop()

			#a tecla < vai para baixo nas escadas, se o jogador estiver nelas
			if key_char == '<':
				if stairs.x == player.x and stairs.y == player.y:
					next_level()

			#a tecla c mostra a informação da personagem
			if key_char == 'c':
				#mostra a informação
				level_up_xp = LEVEL_UP_BASE + player.level * LEVEL_UP_FACTOR
				msgbox('Informacoes da personagem\n\nNivel: ' + str(player.level) + '\nExperiencia: ' + str(player.fighter.xp) + 
					'\nExperiencia para o proximo nivel: ' + str(level_up_xp) + '\n\nMaximo HP: ' + str(player.fighter.max_hp) +
					'\nAtaque: ' + str(player.fighter.power) + '\nDefesa: ' + str(player.fighter.defense), CHARACTER_SCREEN_WIDTH)

			return 'didnt-take-turn'


########################
#FUNÇÃO MENU PRINCIPAL###
##########################
def main_menu():
	img = libtcod.image_load('img/dungeon_e_dogs_title.png')

	while not libtcod.console_is_window_closed():
		#mostra a imagem de fundo com a resolução duas vezes maior que a do console
		libtcod.image_blit_2x(img, 0, 0, 0)

		#mostra o título do jogo e alguns créditos
		libtcod.console_set_default_foreground(0, libtcod.light_amber)
		libtcod.console_print_ex(0, SCREEN_WIDTH/2, SCREEN_HEIGHT/2-4, libtcod.BKGND_NONE, libtcod.CENTER,
			'CALABOU OS & CACHORROS')
		libtcod.console_print_ex(0, SCREEN_WIDTH/2, SCREEN_HEIGHT-4, libtcod.BKGND_NONE, libtcod.CENTER,
			'Um jogo por xxxStanxxx')
		#coloca o caractere 'Ç' na tela
		libtcod.console_put_char( 0, SCREEN_WIDTH/2-4, SCREEN_HEIGHT/2-4, 128, libtcod.BKGND_NONE)
		#libtcod.console_set_char(0, SCREEN_WIDTH/2-4, SCREEN_HEIGHT/2-4, 128)


		#mostra as opções e espera pela escolha do jogador
		choice = menu('', ['Novo Jogo', 'Carregar Ultimo Jogo', 'Sair'], 24)

		if choice == 0: #novo jogo
			new_game()
			play_game()
		if choice == 1: #carrega o jogo
			try:
				load_game()
			except:
				msgbox('\n Nao ha jogo salvo para ser carregado.\n', 24)
				continue
			play_game()
		elif choice == 2: #sai do jogo
			break


###################
#FUNÇÃO NOVO JOGO###
#####################
def new_game():
	global player, inventory, game_msgs, game_state, dungeon_level

	#cria um objeto representando o jogador
	fighter_component = Fighter(hp=100, defense=1, power=2, xp=0, death_function = player_death) ###chamada usando Keyword Arguments do Python(como nas outras funções)
	player = Object(0, 0, '@', 'jogador', libtcod.white, blocks = True, fighter = fighter_component)

	#cria uma variável para controlar o nível do jogador
	player.level = 1

	#cria uma variável para controlar o número de níveis
	dungeon_level = 1

	#cria o mapa(sem desenhar na tela ainda)
	make_map()

	#inicializa o FOV
	initialize_fov()

	#variável para setar o estado atual do jogo (verificar quando o jogador acabou ou não o turno
	#e que outras teclas ele pode apertar ou não)
	game_state = 'playing'

	#cria uma lista com as mensagens do jogo e as cores das mensagens. Inicia vazia
	game_msgs = []

	#cria uma lista para ser o inventário. Inicia vazia
	inventory = []

	#imprime uma mensagem de boas vindas!
	message('Bem vindo estranho! Prepare-se para perecer nos calaboucos perdidos de Ashnoth.', libtcod.red)

	#cria um equipamento inicial para o jogador: uma adaga
	equipment_component = Equipment(slot='mao direita', power_bonus=2)
	obj = Object(0, 0, '-', 'adaga', libtcod.sky, equipment=equipment_component)
	inventory.append(obj)
	equipment_component.equip()
	obj.always_visible = True


########################
#FUNÇÃO INICIALIZA FOV###
##########################
def initialize_fov():
	global fov_recompute, fov_map
	#variável para recomputar o FOV após o player andar
	fov_recompute = True

	#cria um módulo FOV, de a cordo com o mapa gerado
	fov_map = libtcod.map_new(MAP_WIDTH, MAP_HEIGHT)
	for y in range(MAP_HEIGHT):
		for x in range(MAP_WIDTH):
			libtcod.map_set_properties(fov_map, x, y, not map[x][y].block_sight, not map[x][y].blocked)

	libtcod.console_clear(con) #áreas inexploradas começam escuras (que é a cor padrão do background)


############################
#FUNÇÃO PARA SALVAR O JOGO###
##############################
def save_game():
	#abre um novo arquivo para escrever o jogo
	file = shelve.open('savegame', 'n')
	file['map'] = map
	file['objects'] = objects
	file['player_index'] = objects.index(player) #índice do jogador na lista de objetos
	file['inventory'] = inventory
	file['game_msgs'] = game_msgs
	file['game_state'] = game_state
	file['stairs_index'] = objects.index(stairs)
	file['dungeon_level'] = dungeon_level
	file.close()



##############################
#FUNÇÃO PARA CARREGAR O JOGO###
################################
def load_game():
	#abre o arquivo previamente salvo com os dados do jogo
	global map, objects, player, inventory, game_state, game_msgs, stairs, dungeon_level

	file = shelve.open('savegame', 'r')
	map = file['map']
	objects = file['objects']
	player = objects[file['player_index']] #pega o índice do jogador na lista de objetos e acessa ele
	inventory = file['inventory']
	game_msgs = file['game_msgs']
	game_state = file['game_state']
	stairs = objects[file['stairs_index']]
	dungeon_level = file['dungeon_level']
	file.close()

	initialize_fov()


##################
#FUNÇÃO MENSAGEM###
####################
def msgbox(text, width=50):
	menu(text, [], width) # usa a função menu() como um tipo de caixa de mensagem


###############################################
#FUNÇÃO PARA CRIAR O PRÓXIMO NÍVEL DA DUNGEON###
#################################################
def next_level():
	global dungeon_level

	#avança para o próximo nível
	message('Voce tira um tempo para descancar, e recupera sua forca', libtcod.light_violet)
	player.fighter.heal(player.fighter.max_hp / 2) #recupera metade da vida do jogador

	message('Depois de um raro momento de paz, voce desce fundo em direcao ao coracao do calabouco...', libtcod.red)
	dungeon_level += 1 #incrimenta o contador de níveis
	make_map() #cria um novo nível
	initialize_fov()


################################
#FUNÇÃO LOOP PRINCIPAL DO JOGO###
##################################
def play_game():
	global key, mouse

	#variável para verificar a última ação do jogador
	player_action = None

	#cria variáveis para detectar o uso do mouse e do teclado
	mouse = libtcod.Mouse()
	key = libtcod.Key()

	#loop principal
	while not libtcod.console_is_window_closed():

		#verificação de evento do mouse ou do teclado
		libtcod.sys_check_for_event(libtcod.EVENT_KEY_PRESS|libtcod.EVENT_MOUSE,key,mouse)

		#cria a tela
		render_all()

		#a próxima linha atualiza o console, para o jogo atualizar todas as informações que estão acontecendo na tela
		libtcod.console_flush()

		#sobe o nível se necessário
		check_level_up()

		#apaga todos os objetos de suas posições antigas, antes de eles se moverem
		for object in objects:
			object.clear()

		#chama a função handle_keys e sai do jogo se for o caso
		player_action = handle_keys()
		if player_action == 'exit':
			save_game()
			break

		#os monstros fazem o seu turno de ataque
		if game_state == 'playing' and player_action != 'didnt-take-turn':
			for object in objects:
				if object.ai:
					object.ai.take_turn()



########################
#INICIALIZAÇÂO DO JOGO###
##########################

#definindo uma fonte personalizada para o jogo(função especifica da biblioteca libtcodpy)
libtcod.console_set_custom_font('img/terminal8x8_gs_ro.png', libtcod.FONT_TYPE_GREYSCALE | libtcod.FONT_LAYOUT_ASCII_INROW)

#inicializando a tela
#os parâmetros são, em ordem: largura, altura, título e fullscreen(true or false)
libtcod.console_init_root(SCREEN_WIDTH, SCREEN_HEIGHT, 'Calabouços & Cachorros', False)

#cria um novo console, que será o console principal do jogo
con = libtcod.console_new(MAP_WIDTH, MAP_HEIGHT)

#Esta linha limita o FPS do jogo.
libtcod.sys_set_fps(LIMIT_FPS)

#cria um painel GUI na parte baixa da tela
panel = libtcod.console_new(SCREEN_WIDTH, PANEL_HEIGHT)

#chama o menu principal
main_menu()
