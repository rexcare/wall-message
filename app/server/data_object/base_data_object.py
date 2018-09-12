
# Base Data Object

import sys
import uuid
import simplejson as json
import config.config as config
from abc import ABCMeta, abstractmethod


class BaseDataObject(metaclass=ABCMeta):
	"""
	Provides base methods and interface for all proper data objects.

	TODO:
		X add uuid creation on data object create
		- update all 'id's to be 'uuid'
		- add partials caching by uuid to find_many() method
		- add metadata attribute to keep track of:
			- whether or not dataobject exists in the datastore as a record
			- created_ts column
			- updated_ts column
		- refactor test script

		- add consistency options to 'find' methods (skip cache on read)
		- batch queries
		- batch caching of result items
		- asses types of caching currently implemented and research
			alternatives
		- better management of attribute types (int, str, bool, etc.)

	"""


	# properties
	UUID_PROPERTY = 'uuid'

	# metadata
	RECORD_EXISTS_METADATA = 'record_exists'
	CREATED_TS_METADATA = 'created_ts'
	UPDATED_TS_METADATA = 'updated_ts'
	METADATA_FIELDS = [
		RECORD_EXISTS_METADATA,
		CREATED_TS_METADATA,
		UPDATED_TS_METADATA
	]


	def __init__(
		self,
		prop_dict,
		metadata_dict,
		db_driver_class,
		cache_driver_class
	):
		"""
		Data object instance constructor. Configures the database driver, cache
		driver, and state dictionary.

		Args:
			prop_dict (dict): Dictionary representing data object state.
			db_driver_class (class): Database driver class.
			cache_driver_class (class): Cache driver class.

		"""

		# set database driver and cache driver classes and instances
		self.db_driver_class = db_driver_class
		self.cache_driver_class = cache_driver_class
		db_driver, cache_driver = self.__get_drivers(
			db_driver_class=db_driver_class,
			cache_driver_class=cache_driver_class
		)
		self.db_driver = db_driver
		self.cache_driver = cache_driver

		# set state of dataobject as a dictionary
		self.state = prop_dict

		# set metadata initial values
		self.metadata = {
			self.RECORD_EXISTS_METADATA: False,
			self.CREATED_TS_METADATA: None,
			self.UPDATED_TS_METADATA: None
		}

		# replace metadata initial values with passed values
		for key, val in metadata_dict.items():
			if key in self.METADATA_FIELDS:
				self.metadata[key] = val


	########## PRIMARY PUBLIC METHODS ##########


	@classmethod
	def create(
		cls,
		prop_dict={},
		db_driver_class=None,
		cache_driver_class=None
	):
		"""
		Data object creation method. NOTE: Does not save to data store.

		Args:
			prop_dict (dict): Dictionary representing data object state.
			db_driver_class (class): Database driver class.
			cache_driver_class (class): Cache driver class.

		Returns:
			(object) Data object instance.

		"""

		# set uuid upon dataobject creation
		prop_dict[cls.UUID_PROPERTY] = uuid.uuid4().hex

		# use the constructor to set state, database driver and cache driver
		return cls(
			prop_dict=prop_dict,
			db_driver_class=db_driver_class,
			cache_driver_class=cache_driver_class
		)


	@classmethod
	def find_many(
		cls,
		prop_dict={},
		limit=None,
		db_driver_class=None,
		cache_driver_class=None
	):
		"""
		Data object database search method. Search for multiple records matching
		all properties in the prop_dict dictionary.

		Note: There is NO CACHING for this 'batch find' method.

		TODO: add caching to partials

		Args:
			prop_dict (dict): Dictionary representing data object state.
			limit (int): Limit lenth of returned data object list.
			db_driver_class (class): Database driver class.
			cache_driver_class (class): Cache driver class.

		Returns:
			(list) List of data object instances.

		"""

		db_driver, cache_driver = cls.__get_drivers(
			db_driver_class=db_driver_class,
			cache_driver_class=cache_driver_class
		)

		records = db_driver.find_by_fields(
			table_name=cls.TABLE_NAME,
			where_props=prop_dict,
			limit=limit
		)

		instances = [
			cls(
				prop_dict=record,
				db_driver_class=db_driver_class,
				cache_driver_class=cache_driver_class
			)
			for record in records
		]

		return instances


	@classmethod
	def find_one(
		cls,
		prop_dict={},
		db_driver_class=None,
		cache_driver_class=None,
		cache_ttl=None
	):
		"""
		Data object database search method. Search for single records matching
		all properties in the prop_dict dictionary.

		Args:
			prop_dict (dict): Dictionary representing data object state.
			db_driver_class (class): Database driver class.
			cache_driver_class (class): Cache driver class.
			cache_ttl (int): Cache time-to-live in seconds.

		Returns:
			(object) Data object instance.

		"""

		# only check cache if finding solely by uuid
		find_props = list(prop_dict.keys())
		if len(find_props) == 1 and find_props[0] == cls.UUID_PROPERTY:
			instance = cls.__load_from_cache(
				uuid=prop_dict[cls.UUID_PROPERTY],
				db_driver_class=db_driver_class,
				cache_driver_class=cache_driver_class
			)
			if instance is not None:
				instance.__set_to_cache(ttl=cache_ttl)
				return instance

		instance_list = cls.find_many(
			prop_dict=prop_dict,
			limit=1,
			db_driver_class=db_driver_class,
			cache_driver_class=cache_driver_class
		)

		if len(instance_list) > 0:
			return instance_list[0]
		else:
			return None


	@classmethod
	def find_by_uuids(
		cls,
		uuids=[],
		db_driver_class=None,
		cache_driver_class=None,
		cache_ttl=None
	):
		# TODO
		pass


	def get_prop(self, prop_name):
		"""
		Data object property getter method.

		Args:
			prop_name (str): Name of property.

		Returns:
			(mixed) Data object property.

		"""

		return self.state[prop_name]


	def set_prop(self, prop_name, prop_value):
		"""
		Data object property setter method.

		Args:
			prop_name (str): Name of property.
			prop_value (mixed): Property value.

		Returns:
			(bool) Property set success.

		"""

		if prop_name in self.state:
			self.state[prop_name] = prop_value
			return True
		else:
			return False


	def save(self, cache_ttl=None):
		"""
		Data object database save method.

		Args:
			cache_ttl (int): Cache time-to-live in seconds.

		Returns:
			(object) Data object instance or None if save fails.

		TODO: requires major refactor for use of uuids instead of
			auto-incremented ids

		"""

		result = None

		# existing record
		if self.UUID_PROPERTY in self.state:
			record_update_count = self.db_driver.update_by_fields(
				table_name=self.TABLE_NAME,
				value_props=self.state,
				where_props={
					self.UUID_PROPERTY: self.get_prop(self.UUID_PROPERTY)
				}
			)
			result = self if record_update_count == 1 else None
		# new record
		else:
			new_record_id = self.db_driver.insert(
				table_name=self.TABLE_NAME,
				value_props=self.state
			)
			if new_record_id > 0:
				result = self.find_one(prop_dict={ 'id': new_record_id })

		if result is not None:
			result.__set_to_cache(ttl=cache_ttl)

		return result


	def delete(self):
		"""
		Data object database delete method.

		Returns:
			(bool) Database delete success.

		"""

		record_delete_count = self.db_driver.delete_by_fields(
			table_name=self.TABLE_NAME,
			where_props={
				self.UUID_PROPERTY: self.get_prop(self.UUID_PROPERTY)
			}
		)
		if record_delete_count > 0:
			self.__delete_from_cache()
			return True
		else:
			return False


	########## SECONDARY PUBLIC METHODS ##########


	@classmethod
	def get_drivers(cls, db_driver_class=None, cache_driver_class=None):

		db_driver_class = db_driver_class \
		if db_driver_class is not None \
		else cls.DEFAULT_DB_DRIVER_CLASS

		cache_driver_class = cache_driver_class \
		if cache_driver_class is not None \
		else cls.DEFAULT_CACHE_DRIVER_CLASS

		db_driver = None
		cache_driver = None

		if db_driver_class is not None:
			db_driver = db_driver_class(
				database_name=config.MYSQL_DB_NAME
			)

		if cache_driver_class is not None:
			cache_driver = cache_driver_class()

		return db_driver, cache_driver


	@classmethod
	def construct_cache_key(cls, uuid):
		cache_key = '{0}_uuid={1}'.format(
			cls.TABLE_NAME,
			uuid
		)
		return cache_key


	def set_to_cache(self, ttl=None):
		cache_key = self.construct_cache_key(
			uuid=self.get_prop(self.UUID_PROPERTY)
		)
		cache_value = self.to_dict()
		ttl = ttl if ttl is not None else self.DEFAULT_CACHE_TTL
		self.cache_driver.set(
			key=cache_key,
			value=cache_value,
			ttl=ttl
		)


	@classmethod
	def set_batch_to_cache(
		cls,
		dataobjects=[],
		ttl=None,
		db_driver_class,
		cache_driver_class
	):
		db_driver, cache_driver = cls.get_drivers(
			db_driver_class=db_driver_class,
			cache_driver_class=cache_driver_class
		)
		cache_items = {}
		for DO in dataobjects:
			cache_key = cls.construct_cache_key(
				uuid=DO.get_prop(cls.UUID_PROPERTY)
			)
			cache_value = DO.to_dict()
			cache_items[cache_key] = cache_value
		cache_driver.batch_set(items=cache_items, ttl=ttl)


	def delete_from_cache(self):
		cache_key = self.construct_cache_key(
			uuid=self.get_prop(self.UUID_PROPERTY)
		)
		self.cache_driver.delete(cache_key)


	@classmethod
	def delete_batch_from_cache(cls, dataobjects=[]):
		db_driver, cache_driver = cls.get_drivers(
			db_driver_class=db_driver_class,
			cache_driver_class=cache_driver_class
		)
		cache_keys = [
			cls.construct_cache_key(uuid=DO.get_prop(cls.UUID_PROPERTY))
			for DO in dataobjects
		]
		return cache_driver.batch_delete(keys=cache_keys)


	@classmethod
	def load_from_cache_by_uuids(
		cls,
		uuids,
		db_driver_class,
		cache_driver_class
	):
		db_driver, cache_driver = cls.get_drivers(
			db_driver_class=db_driver_class,
			cache_driver_class=cache_driver_class
		)
		cache_keys = [
			cls.construct_cache_key(uuid=uuid)
			for uuid in uuids
		]
		cached_values = cache_driver.batch_get(keys=cache_keys)
		# TODO...


	@classmethod
	def load_from_cache_by_uuid(cls, uuid, db_driver_class, cache_driver_class):
		db_driver, cache_driver = cls.get_drivers(
			db_driver_class=db_driver_class,
			cache_driver_class=cache_driver_class
		)
		cache_key = cls.construct_cache_key(uuid=uuid)
		cached_value = cache_driver.get(cache_key)
		if cached_value is not None:
			instance = cls(
				prop_dict=cached_value['state'],
				metadata=cached_value['metadata'],
				db_driver_class=db_driver_class,
				cache_driver_class=cache_driver_class
			)
			return instance
		else:
			return None


	########## UTILITY PUBLIC METHODS ##########


	def to_dict(self):
		"""
		Get data object's state and metadata in dictionary format.

		Returns:
			(dict) Dictionary representation of data object.

		"""

		return {
			'state': self.state,
			'metadata': self.metadata
		}


	def to_json(self, pretty=False):
		"""
		Get data object's state and metadata formatted as JSON string.

		Args:
			pretty (bool): Option for getting JSON string in pretty format.

		Returns:
			(str) JSON string.

		"""

		if pretty:
			return json.dumps(self.to_dict(), sort_keys=True, indent=2)
		else:
			return json.dumps(self.to_dict())


	########## PRIVATE METHODS ##########


	def __get_prop_names(self):
		return self.db_driver.get_table_field_names(self.TABLE_NAME)

