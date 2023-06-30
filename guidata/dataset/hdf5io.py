# -*- coding: utf-8 -*-
#
# Copyright © 2009-2010 CEA
# Pierre Raybaut
# Licensed under the terms of the CECILL License
# (see guidata/__init__.py for details)

"""
Reader and Writer for the serialization of DataSets into HDF5 files
"""

from __future__ import annotations

import sys
from collections.abc import Callable, Sequence
from typing import Any
from uuid import uuid1

import h5py
import numpy as np

from guidata.dataset.iniio import BaseIOHandler, WriterMixin


class TypeConverter:
    """Handles conversion between types for HDF5 serialization.

    Args:
        to_type (Any): The target type for the HDF5 representation.
        from_type (Any | None): The original type from the HDF5 representation.
                                Defaults to `to_type` if not specified.

    Note:
        Instances of this class are used to ensure data consistency when
        serializing and deserializing data to and from HDF5 format.
    """

    def __init__(
        self,
        to_type: Callable[[Any], Any],
        from_type: Callable[[Any], Any] | None = None,
    ) -> None:
        self._to_type = to_type
        self._from_type = to_type if from_type is None else from_type

    def to_hdf(self, value: Any) -> Any:
        """Converts the value to the target type for HDF5 serialization.

        Args:
            value (Any): The value to be converted.

        Returns:
            Any: The converted value in the target type.

        Raises:
            Exception: If the conversion to the target type fails.
        """
        try:
            return self._to_type(value)
        except Exception:
            print("ERR", repr(value), file=sys.stderr)
            raise

    def from_hdf(self, value: Any) -> Any:
        """Converts the value from the HDF5 representation to target type.

        Args:
            value (Any): The HDF5 value to be converted.

        Returns:
            Any: The converted value in the original type.
        """
        return self._from_type(value)


try:
    unicode_hdf = TypeConverter(
        lambda x: x.encode("utf-8"), lambda x: str(x, encoding="utf-8")
    )
except Exception:
    unicode_hdf = TypeConverter(lambda x: x.encode("utf-8"), lambda x: x)
int_hdf = TypeConverter(int)


class Attr:
    """Helper class representing class attribute for HDF5 serialization.

    Args:
        hdf_name (str): Name of the attribute in the HDF5 file.
        struct_name (str | None): Name of the attribute in the object.
                                  Defaults to `hdf_name` if not specified.
        type (TypeConverter | None): Attribute type. If None, type is guessed.
        optional (bool): If True, attribute absence will not raise error.

    Note:
        This class manages serialization and deserialization of the object's
        attributes to and from HDF5 format.
    """

    def __init__(
        self,
        hdf_name: str,
        struct_name: str | None = None,
        type: TypeConverter | None = None,
        optional: bool = False,
    ) -> None:
        self.hdf_name = hdf_name
        self.struct_name = hdf_name if struct_name is None else struct_name
        self.type = type
        self.optional = optional

    def get_value(self, struct: Any) -> Any:
        """Get the value of the attribute from the object.

        Args:
            struct (Any): The object to extract the attribute from.

        Returns:
            Any: The value of the attribute.
        """
        if self.optional:
            return getattr(struct, self.struct_name, None)
        return getattr(struct, self.struct_name)

    def set_value(self, struct: Any, value: Any) -> None:
        """Set the value of the attribute in the object.

        Args:
            struct (Any): The object to set the attribute value in.
            value (Any): The value to set.
        """
        setattr(struct, self.struct_name, value)

    def save(self, group: h5py.Group, struct: Any) -> None:
        """Save the attribute to an HDF5 group.

        Args:
            group (h5py.Group): The HDF5 group to save the attribute to.
            struct (Any): The object to save the attribute from.

        Raises:
            Exception: If an error occurs while saving the attribute.
        """
        value = self.get_value(struct)
        if self.optional and value is None:
            if self.hdf_name in group.attrs:
                del group.attrs[self.hdf_name]
            return
        if self.type is not None:
            value = self.type.to_hdf(value)
        try:
            group.attrs[self.hdf_name] = value
        except Exception:  # pylint: disable=broad-except
            print("ERROR saving:", repr(value), "into", self.hdf_name, file=sys.stderr)
            raise

    def load(self, group: h5py.Group, struct: Any) -> None:
        """Load the attribute from an HDF5 group into an object.

        Args:
            group (h5py.Group): The HDF5 group to load the attribute from.
            struct (Any): The object to load the attribute into.

        Raises:
            KeyError: If the attribute is not found in the HDF5 group.
        """
        if self.optional and self.hdf_name not in group.attrs:
            self.set_value(struct, None)
            return
        try:
            value = group.attrs[self.hdf_name]
        except KeyError as err:
            raise KeyError(f"Unable to locate attribute {self.hdf_name}") from err
        if self.type is not None:
            value = self.type.from_hdf(value)
        self.set_value(struct, value)


def createdset(group: h5py.Group, name: str, value: np.ndarray | list) -> None:
    """
    Creates a dataset in the provided HDF5 group.

    Args:
        group (h5py.Group): The group in the HDF5 file to add the dataset to.
        name (str): The name of the dataset.
        value (np.ndarray or list): The data to be stored in the dataset.

    Returns:
        None
    """
    group.create_dataset(name, compression=None, data=value)


class Dset(Attr):
    """
    Class for generic load/save for an hdf5 dataset.
    Handles the conversion of the scalar value, if any.

    Args:
        hdf_name (str): The name of the HDF5 attribute.
        struct_name (str, optional): The name of the structure. Defaults to None.
        type (type, optional): The expected data type of the attribute.
            Defaults to None.
        scalar (callable, optional): Function to convert the scalar value, if any.
            Defaults to None.
        optional (bool, optional): Whether the attribute is optional. Defaults to False.
    """

    def __init__(
        self,
        hdf_name: str,
        struct_name: str | None = None,
        type: type | None = None,
        scalar: Callable | None = None,
        optional: bool = False,
    ) -> None:
        super().__init__(hdf_name, struct_name, type, optional)
        self.scalar = scalar

    def save(self, group: h5py.Group, struct: Any) -> None:
        """
        Save the attribute to the given HDF5 group.

        Args:
            group (h5py.Group): The group in the HDF5 file to save the attribute to.
            struct (any): The structure containing the attribute.

        Returns:
            None
        """
        value = self.get_value(struct)
        if isinstance(value, float):
            value = np.float64(value)
        elif isinstance(value, int):
            value = np.int32(value)
        if value is None or value.size == 0:
            value = np.array([0.0])
        if value.shape == ():
            value = value.reshape((1,))
        group.require_dataset(
            self.hdf_name,
            shape=value.shape,
            dtype=value.dtype,
            data=value,
            compression="gzip",
            compression_opts=1,
        )

    def load(self, group: h5py.Group, struct: Any) -> None:
        """
        Load the attribute from the given HDF5 group.

        Args:
            group (h5py.Group): The group in the HDF5 file to load the attribute from.
            struct (any): The structure to load the attribute into.

        Raises:
            KeyError: If the attribute cannot be found in the HDF5 group.

        Returns:
            None
        """
        if self.optional:
            if self.hdf_name not in group:
                self.set_value(struct, None)
                return
        try:
            value = group[self.hdf_name][...]
        except KeyError as err:
            raise KeyError("Unable to locate dataset {}".format(self.hdf_name)) from err
        if self.scalar is not None:
            value = self.scalar(value)
        self.set_value(struct, value)


class Dlist(Dset):
    """
    Class for handling lists in HDF5 datasets. Inherits from the Dset class.

    Overrides the get_value and set_value methods from the Dset class to
    handle lists specifically.

    Args:
        hdf_name (str): The name of the HDF5 attribute.
        struct_name (str, optional): The name of the structure. Defaults to None.
        type (type, optional): The expected data type of the attribute.
            Defaults to None.
        scalar (callable, optional): Function to convert the scalar value, if any.
            Defaults to None.
        optional (bool, optional): Whether the attribute is optional. Defaults to False.
    """

    def get_value(self, struct: Any) -> np.ndarray:
        """
        Returns the value of the attribute in the given structure as a numpy array.

        Args:
            struct (any): The structure containing the attribute.

        Returns:
            np.ndarray: The value of the attribute in the given structure as a
                numpy array.
        """
        return np.array(getattr(struct, self.struct_name))

    def set_value(self, struct: Any, value: np.ndarray) -> None:
        """
        Sets the value of the attribute in the given structure to a list containing
        the values of the given numpy array.

        Args:
            struct (any): The structure in which to set the attribute.
            value (np.ndarray): A numpy array containing the values to set the
                attribute to.

        Returns:
            None
        """
        setattr(struct, self.struct_name, list(value))


# ==============================================================================
# Base HDF5 Store object: do not break API compatibility here as this class is
# used in various critical projects for saving/loading application data
# ==============================================================================
class H5Store:
    """
    Class for managing HDF5 files.

    Args:
        filename (str): The name of the HDF5 file.
    """

    def __init__(self, filename: str) -> None:
        self.filename = filename
        self.h5 = None

    def open(self, mode: str = "a") -> h5py._hl.files.File:
        """
        Opens an HDF5 file in the given mode.

        Args:
            mode (str, optional): The mode in which to open the file. Defaults to "a".

        Returns:
            h5py._hl.files.File: The opened HDF5 file.

        Raises:
            Exception: If there is an error while trying to open the file.
        """
        if self.h5:
            return self.h5
        try:
            self.h5 = h5py.File(self.filename, mode=mode)
        except Exception:
            print(
                "Error trying to load:",
                self.filename,
                "in mode:",
                mode,
                file=sys.stderr,
            )
            raise
        return self.h5

    def close(self) -> None:
        """
        Closes the HDF5 file if it is open.

        Returns:
            None
        """
        if self.h5:
            self.h5.close()
        self.h5 = None

    def __enter__(self) -> "H5Store":
        """
        Support for 'with' statement.

        Returns:
            H5Store: The instance of the class itself.
        """
        return self

    def __exit__(self, *args) -> None:
        """
        Support for 'with' statement. Closes the HDF5 file on exiting the 'with' block.

        Returns:
            None
        """
        self.close()

    def generic_save(self, parent: Any, source: Any, structure: list[Attr]) -> None:
        """
        Saves the data from source into the file using 'structure' as a descriptor.

        Args:
            parent (any): The parent HDF5 group.
            source (any): The source of the data to save.
            structure (List[Attr]): A list of attribute descriptors (Attr, Dset,
                Dlist, etc.) that describe the conversion of data and the names
                of the attributes in the source and in the file.

        Returns:
            None
        """
        for instr in structure:
            instr.save(parent, source)

    def generic_load(self, parent: Any, dest: Any, structure: list[Attr]) -> None:
        """
        Loads the data from the file into 'dest' using 'structure' as a descriptor.

        Args:
            parent (any): The parent HDF5 group.
            dest (any): The destination to load the data into.
            structure (List[Attr]): A list of attribute descriptors (Attr, Dset,
                Dlist, etc.) that describe the conversion of data and the names
                of the attributes in the file and in the destination.

        Returns:
            None

        Raises:
            Exception: If there is an error while trying to load an item.
        """
        for instr in structure:
            try:
                instr.load(parent, dest)
            except Exception as err:
                print("Error loading HDF5 item:", instr.hdf_name, file=sys.stderr)
                raise err


# ==============================================================================
# HDF5 reader/writer: do not break API compatibility here as this class is
# used in various critical projects for saving/loading application data and
# in guiqwt for saving/loading plot items.
# ==============================================================================
class HDF5Handler(H5Store, BaseIOHandler):
    """
    Base HDF5 I/O Handler object. Inherits from H5Store and BaseIOHandler.

    Args:
        filename (str): The name of the HDF5 file.
    """

    def __init__(self, filename: str) -> None:
        super().__init__(filename)
        self.option = []

    def get_parent_group(self) -> h5py._hl.group.Group:
        """
        Returns the parent group in the HDF5 file based on the current option.

        Returns:
            h5py._hl.group.Group: The parent group in the HDF5 file.
        """
        parent = self.h5
        for option in self.option[:-1]:
            parent = parent.require_group(option)
        return parent


class HDF5Writer(HDF5Handler, WriterMixin):
    """
    Writer for HDF5 files. Inherits from HDF5Handler and WriterMixin.

    Args:
        filename (str): The name of the HDF5 file.
    """

    def __init__(self, filename: str) -> None:
        super().__init__(filename)
        self.open("w")

    def write_any(self, val: Any) -> None:
        """
        Write the value to the HDF5 file as an attribute.

        Args:
            val (any): The value to write.

        Returns:
            None
        """
        group = self.get_parent_group()
        group.attrs[self.option[-1]] = val

    write_int = write_float = write_any

    def write_bool(self, val: bool) -> None:
        """
        Write the boolean value to the HDF5 file as an attribute.

        Args:
            val (bool): The boolean value to write.

        Returns:
            None
        """
        self.write_int(int(val))

    write_str = write_any

    def write_unicode(self, val: str) -> None:
        """
        Write the Unicode string value to the HDF5 file as an attribute.

        Args:
            val (str): The Unicode string value to write.

        Returns:
            None
        """
        group = self.get_parent_group()
        group.attrs[self.option[-1]] = val.encode("utf-8")

    write_unicode = write_str

    def write_array(self, val: np.ndarray) -> None:
        """
        Write the numpy array value to the HDF5 file.

        Args:
            val (np.ndarray): The numpy array value to write.

        Returns:
            None
        """
        group = self.get_parent_group()
        group[self.option[-1]] = val

    write_sequence = write_any

    def write_none(self) -> None:
        """
        Write a None value to the HDF5 file as an attribute.

        Returns:
            None
        """
        group = self.get_parent_group()
        group.attrs[self.option[-1]] = ""

    def write_object_list(self, seq: Sequence[Any] | None, group_name: str) -> None:
        """
        Write an object sequence to the HDF5 file in a group.
        Objects must implement the DataSet-like `serialize` method.

        Args:
            seq (Sequence[Any], optional): The object sequence to write.
                Defaults to None.
            group_name (str): The name of the group in which to write the objects.

        Returns:
            None
        """
        with self.group(group_name):
            if seq is None:
                self.write_none()
            else:
                ids = []
                for obj in seq:
                    guid = bytes(str(uuid1()), "utf-8")
                    ids.append(guid)
                    with self.group(guid):
                        if obj is None:
                            self.write_none()
                        else:
                            obj.serialize(self)
                self.write(ids, "IDs")


class HDF5Reader(HDF5Handler):
    """
    Reader for HDF5 files. Inherits from HDF5Handler.

    Args:
        filename (str): The name of the HDF5 file.
    """

    def __init__(self, filename: str):
        super().__init__(filename)
        self.open("r")

    def read(
        self,
        group_name: str | None = None,
        func: Callable[[], Any] | None = None,
        instance: Any | None = None,
    ) -> Any:
        """
        Read a value from the current group or specified group_name.

        Args:
            group_name (str, optional): The name of the group to read from.
                Defaults to None.
            func (Callable[[], Any], optional): The function to use for reading
                the value. Defaults to None.
            instance (Any, optional): An object that implements the DataSet-like
                `deserialize` method. Defaults to None.

        Returns:
            Any: The read value.
        """
        if group_name:
            self.begin(group_name)
        if instance is None:
            if func is None:
                func = self.read_any
            val = func()
        else:
            group = self.get_parent_group()
            if group_name in group.attrs:
                # This is an attribute (not a group), meaning that
                # the object was None when deserializing it
                val = None
            else:
                instance.deserialize(self)
                val = instance
        if group_name:
            self.end(group_name)
        return val

    def read_any(self) -> str | bytes:
        """
        Read a value from the current group as a generic type.

        Returns:
            Union[str, bytes]: The read value.
        """
        group = self.get_parent_group()
        value = group.attrs[self.option[-1]]
        if isinstance(value, bytes):
            return value.decode("utf-8")
        else:
            return value

    def read_bool(self) -> bool | None:
        """
        Read a boolean value from the current group.

        Returns:
            Optional[bool]: The read boolean value.
        """
        val = self.read_any()
        if val != "":
            return bool(val)

    def read_int(self) -> int | None:
        """
        Read an integer value from the current group.

        Returns:
            Optional[int]: The read integer value.
        """
        val = self.read_any()
        if val != "":
            return int(val)

    def read_float(self) -> float | None:
        """
        Read a float value from the current group.

        Returns:
            Optional[float]: The read float value.
        """
        val = self.read_any()
        if val != "":
            return float(val)

    read_unicode = read_str = read_any

    def read_array(self) -> np.ndarray:
        """
        Read a numpy array from the current group.

        Returns:
            np.ndarray: The read numpy array.
        """
        group = self.get_parent_group()
        return group[self.option[-1]][...]

    def read_sequence(self) -> list[Any]:
        """
        Read a sequence from the current group.

        Returns:
            List[Any]: The read sequence.
        """
        group = self.get_parent_group()
        return list(group.attrs[self.option[-1]])

    def read_object_list(
        self,
        group_name: str,
        klass: type[Any],
        progress_callback: Callable[[int], bool] | None = None,
    ) -> list[Any]:
        """
        Read an object sequence from a group.

        Objects must implement the DataSet-like `deserialize` method.
        `klass` is the object class which constructor requires no argument.

        progress_callback: if not None, this function is called with
        an integer argument (progress: 0 --> 100). Function returns the
        `cancel` state (True: progress dialog has been canceled, False
        otherwise)
        """
        with self.group(group_name):
            try:
                ids = self.read("IDs", func=self.read_sequence)
            except ValueError:
                # None was saved instead of list of objects
                self.end("IDs")
                return
            seq = []
            count = len(ids)
            for idx, name in enumerate(ids):
                if progress_callback is not None:
                    if progress_callback(int(100 * float(idx) / count)):
                        break
                with self.group(name):
                    try:
                        group = self.get_parent_group()
                        if name in group.attrs:
                            # This is an attribute (not a group), meaning that
                            # the object was None when deserializing it
                            obj = None
                        else:
                            obj = klass()
                            obj.deserialize(self)
                    except ValueError as err:
                        break
                seq.append(obj)
        return seq

    read_none = read_any