# -*- coding: utf-8 -*-
#
# Licensed under the terms of the BSD 3-Clause
# (see guidata/LICENSE for details)

"""
Data items
----------

Numeric items
^^^^^^^^^^^^^

.. autoclass:: FloatItem
    :members:

.. autoclass:: IntItem
    :members:

.. autoclass:: FloatArrayItem
    :members:

Text items
^^^^^^^^^^

.. autoclass:: StringItem
    :members:

.. autoclass:: TextItem
    :members:

Date and time items
^^^^^^^^^^^^^^^^^^^

.. autoclass:: DateItem
    :members:

.. autoclass:: DateTimeItem
    :members:

Color items
^^^^^^^^^^^

.. autoclass:: ColorItem
    :members:

File items
^^^^^^^^^^

.. autoclass:: FileSaveItem
    :members:

.. autoclass:: FileOpenItem
    :members:

.. autoclass:: FilesOpenItem
    :members:

.. autoclass:: DirectoryItem
    :members:

Choice items
^^^^^^^^^^^^

.. autoclass:: BoolItem
    :members:

.. autoclass:: ChoiceItem
    :members:

.. autoclass:: MultipleChoiceItem
    :members:

.. autoclass:: ImageChoiceItem
    :members:

Other items
^^^^^^^^^^^

.. autoclass:: ButtonItem
    :members:

.. autoclass:: DictItem
    :members:

.. autoclass:: FontFamilyItem
    :members:
"""

import collections.abc
import datetime
import os
import re
from typing import TYPE_CHECKING, Any, Callable, List, Optional, Tuple, Type, Union

from guidata.config import _
from guidata.dataset.datatypes import DataItem, DataSet, ItemProperty
from guidata.dataset.iniio import UserConfigReader, UserConfigWriter
from guidata.qthelpers import exec_dialog
from numpy import ndarray

if TYPE_CHECKING:  # pragma: no cover
    from guidata.dataset.hdf5io import HDF5Reader, HDF5Writer
    from guidata.dataset.jsonio import JSONReader, JSONWriter


class NumericTypeItem(DataItem):
    """
    Numeric data item
    * label [string]: name
    * default [int]: default value (optional)
    * min [int]: minimum value (optional)
    * max [int]: maximum value (optional)
    * nonzero [bool]: if True, zero is not a valid value (optional)
    * unit [string]: physical unit (optional)
    * even [bool]: if True, even values are valid, if False,
        odd values are valid if None (default), ignored (optional)
    * slider [bool]: if True, shows a slider widget right after the line
        edit widget (default is False)
    * help [string]: text shown in tooltip (optional)
    * check [bool]: if False, value is not checked (optional, default=True)
    """

    type: Callable = None

    def __init__(
        self,
        label: str,
        default: Optional[Union[float, int]] = None,
        min: Optional[Union[float, int]] = None,
        max: Optional[Union[float, int]] = None,
        nonzero: Optional[bool] = None,
        unit: str = "",
        help: str = "",
        check: bool = True,
    ) -> None:
        DataItem.__init__(self, label, default=default, help=help)
        self.set_prop("data", min=min, max=max, nonzero=nonzero, check_value=check)
        self.set_prop("display", unit=unit)

    def get_auto_help(self, instance: DataSet) -> str:
        """Override DataItem method"""
        auto_help = {int: _("integer"), float: _("float")}[self.type]
        _min = self.get_prop_value("data", instance, "min")
        _max = self.get_prop_value("data", instance, "max")
        nonzero = self.get_prop_value("data", instance, "nonzero")
        unit = self.get_prop_value("display", instance, "unit")
        if _min is not None and _max is not None:
            auto_help += _(" between ") + str(_min) + _(" and ") + str(_max)
        elif _min is not None:
            auto_help += _(" higher than ") + str(_min)
        elif _max is not None:
            auto_help += _(" lower than ") + str(_max)
        if nonzero:
            auto_help += ", " + _("non zero")
        if unit:
            auto_help += ", %s %s" % (_("unit:"), unit)
        return auto_help

    def format_string(
        self, instance: "DataSet", value: Union[float, int], fmt: str, func: Callable
    ) -> str:
        """Override DataItem method"""
        text = fmt % (func(value),)
        # We add directly the unit to 'text' (instead of adding it
        # to 'fmt') to avoid string formatting error if '%' is in unit
        unit = self.get_prop_value("display", instance, "unit", "")
        if unit:
            text += " " + unit
        return text

    def check_value(self, value: Union[float, int]) -> bool:
        """Override DataItem method"""
        if not self.get_prop("data", "check_value", True):
            return True
        if not isinstance(value, self.type):
            return False
        if self.get_prop("data", "nonzero") and value == 0:
            return False
        _min = self.get_prop("data", "min")
        if _min is not None:
            if value < _min:
                return False
        _max = self.get_prop("data", "max")
        if _max is not None:
            if value > _max:
                return False
        return True

    def from_string(self, value: str) -> Optional[Any]:
        """Override DataItem method"""
        # String may contains numerical operands:
        if re.match(r"^([\d\(\)\+/\-\*.]|e)+$", value):
            try:
                return self.type(eval(value))
            except:
                pass
        return None


class FloatItem(NumericTypeItem):
    """
    Construct a float data item
        * label [string]: name
        * default [float]: default value (optional)
        * min [float]: minimum value (optional)
        * max [float]: maximum value (optional)
        * slider [bool]: if True, shows a slider widget right after the line
          edit widget (default is False)
        * step [float]: step between tick values with a slider widget (optional)
        * nonzero [bool]: if True, zero is not a valid value (optional)
        * unit [string]: physical unit (optional)
        * help [string]: text shown in tooltip (optional)
        * check [bool]: if False, value is not checked (optional, default=True)
    """

    type = float

    def __init__(
        self,
        label: str,
        default: Optional[float] = None,
        min: Optional[float] = None,
        max: Optional[float] = None,
        nonzero: Optional[bool] = None,
        unit: str = "",
        step: float = 0.1,
        slider: bool = False,
        help: str = "",
        check: bool = True,
    ) -> None:
        super().__init__(
            label,
            default=default,
            min=min,
            max=max,
            nonzero=nonzero,
            unit=unit,
            help=help,
            check=check,
        )
        self.set_prop("display", slider=slider)
        self.set_prop("data", step=step)

    def get_value_from_reader(
        self, reader: Union["HDF5Reader", "JSONReader", "UserConfigReader"]
    ) -> float:
        """Reads value from the reader object, inside the try...except
        statement defined in the base item `deserialize` method"""
        return reader.read_float()


class IntItem(NumericTypeItem):
    """
    Construct an integer data item
        * label [string]: name
        * default [int]: default value (optional)
        * min [int]: minimum value (optional)
        * max [int]: maximum value (optional)
        * nonzero [bool]: if True, zero is not a valid value (optional)
        * unit [string]: physical unit (optional)
        * even [bool]: if True, even values are valid, if False,
          odd values are valid if None (default), ignored (optional)
        * slider [bool]: if True, shows a slider widget right after the line
          edit widget (default is False)
        * help [string]: text shown in tooltip (optional)
        * check [bool]: if False, value is not checked (optional, default=True)
    """

    type = int

    def __init__(
        self,
        label: str,
        default: Optional[int] = None,
        min: Optional[int] = None,
        max: Optional[int] = None,
        nonzero: Optional[bool] = None,
        unit: str = "",
        even: Optional[bool] = None,
        slider: bool = False,
        help: str = "",
        check: bool = True,
    ) -> None:
        super().__init__(
            label,
            default=default,
            min=min,
            max=max,
            nonzero=nonzero,
            unit=unit,
            help=help,
            check=check,
        )
        self.set_prop("data", even=even)
        self.set_prop("display", slider=slider)

    def get_auto_help(self, instance: "DataSet") -> str:
        """Override DataItem method"""
        auto_help = super().get_auto_help(instance)
        even = self.get_prop_value("data", instance, "even")
        if even is not None:
            if even:
                auto_help += ", " + _("even")
            else:
                auto_help += ", " + _("odd")
        return auto_help

    def check_value(self, value: Any) -> bool:
        """Override DataItem method"""
        if not self.get_prop("data", "check_value", True):
            return True
        valid = super().check_value(value)
        if not valid:
            return False
        even = self.get_prop("data", "even")
        if even is not None:
            is_even = value // 2 == value / 2.0
            if (even and not is_even) or (not even and is_even):
                return False
        return True

    def get_value_from_reader(
        self, reader: Union["HDF5Reader", "JSONReader", "UserConfigReader"]
    ) -> Any:
        """Reads value from the reader object, inside the try...except
        statement defined in the base item `deserialize` method"""
        return reader.read_int()


class StringItem(DataItem):
    """
    Construct a string data item
        * label [string]: name
        * default [string]: default value (optional)
        * help [string]: text shown in tooltip (optional)
        * notempty [bool]: if True, empty string is not a valid value (opt.)
        * wordwrap [bool]: toggle word wrapping (optional)
    """

    type: Any = str

    def __init__(
        self,
        label: str,
        default: Optional[str] = None,
        notempty: Optional[bool] = None,
        wordwrap: bool = False,
        help: str = "",
    ) -> None:
        DataItem.__init__(self, label, default=default, help=help)
        self.set_prop("data", notempty=notempty)
        self.set_prop("display", wordwrap=wordwrap)

    def check_value(self, value: Any) -> bool:
        """Override DataItem method"""
        notempty = self.get_prop("data", "notempty")
        if notempty and not value:
            return False
        return True

    def from_string(self, value: str) -> str:
        """Override DataItem method"""
        return value

    def get_value_from_reader(
        self, reader: Union["HDF5Reader", "JSONReader", "UserConfigReader"]
    ) -> Any:
        """Reads value from the reader object, inside the try...except
        statement defined in the base item `deserialize` method"""
        return reader.read_unicode()


class TextItem(StringItem):
    """
    Construct a text data item (multiline string)
        * label [string]: name
        * default [string]: default value (optional)
        * help [string]: text shown in tooltip (optional)
        * notempty [bool]: if True, empty string is not a valid value (opt.)
        * wordwrap [bool]: toggle word wrapping (optional)
    """

    def __init__(
        self,
        label: str,
        default: Optional[str] = None,
        notempty: Optional[bool] = None,
        wordwrap: bool = True,
        help: str = "",
    ) -> None:
        StringItem.__init__(
            self,
            label,
            default=default,
            notempty=notempty,
            wordwrap=wordwrap,
            help=help,
        )


class BoolItem(DataItem):
    """
    Construct a boolean data item
        * text [string]: form's field name (optional)
        * label [string]: name
        * default [string]: default value (optional)
        * help [string]: text shown in tooltip (optional)
        * check [bool]: if False, value is not checked (optional, default=True)
    """

    type = bool

    def __init__(
        self,
        text: str = "",
        label: str = "",
        default: Optional[bool] = None,
        help: str = "",
        check: bool = True,
    ) -> None:
        DataItem.__init__(self, label, default=default, help=help, check=check)
        self.set_prop("display", text=text)

    def get_value_from_reader(
        self, reader: Union["HDF5Reader", "JSONReader", "UserConfigReader"]
    ) -> bool:
        """Reads value from the reader object, inside the try...except
        statement defined in the base item `deserialize` method"""
        return reader.read_bool()


class DateItem(DataItem):
    """
    Construct a date data item.
        * text [string]: form's field name (optional)
        * label [string]: name
        * default [datetime.date]: default value (optional)
        * help [string]: text shown in tooltip (optional)
    """

    type = datetime.date


class DateTimeItem(DateItem):
    """
    Construct a date time data item.
        * text [string]: form's field name (optional)
        * label [string]: name
        * default [datetime.date]: default value (optional)
        * help [string]: text shown in tooltip (optional)
    """

    pass


class ColorItem(StringItem):
    """
    Construct a color data item
        * label [string]: name
        * default [string]: default value (optional)
        * help [string]: text shown in tooltip (optional)
        * check [bool]: if False, value is not checked (optional, default=True)

    Color values are encoded as hexadecimal strings or Qt color names
    """

    def check_value(self, value: str) -> bool:
        """Override DataItem method"""
        if not self.get_prop("data", "check_value", True):
            return True
        if not isinstance(value, self.type):
            return False
        from guidata.qthelpers import text_to_qcolor

        return text_to_qcolor(value).isValid()

    def get_value_from_reader(
        self, reader: Union["HDF5Reader", "JSONReader", "UserConfigReader"]
    ) -> str:
        """Reads value from the reader object, inside the try...except
        statement defined in the base item `deserialize` method"""
        # Using read_str converts `numpy.string_` to `str` -- otherwise,
        # when passing the string to a QColor Qt object, any numpy.string_ will
        # be interpreted as no color (black)
        return reader.read_str()


class FileSaveItem(StringItem):
    """
    Construct a path data item for a file to be saved
        * label [string]: name
        * formats [string (or string list)]: wildcard filter
        * default [string]: default value (optional)
        * basedir [string]: default base directory (optional)
        * help [string]: text shown in tooltip (optional)
        * check [bool]: if False, value is not checked (optional, default=True)
    """

    def __init__(
        self,
        label: str,
        formats: Union[Tuple[str, ...], str] = "*",
        default: Optional[Union[List[str], str]] = None,
        basedir: Optional[str] = None,
        all_files_first: bool = False,
        help: str = "",
        check: bool = True,
    ) -> None:
        DataItem.__init__(self, label, default=default, help=help, check=check)
        if isinstance(formats, str):
            formats = [formats]  # type:ignore
        self.set_prop("data", formats=formats)
        self.set_prop("data", basedir=basedir)
        self.set_prop("data", all_files_first=all_files_first)

    def get_auto_help(self, instance: "DataSet") -> str:
        """Override DataItem method"""
        formats = self.get_prop("data", "formats")
        return (
            _("all file types")
            if formats == ["*"]
            else _("supported file types:") + " *.%s" % ", *.".join(formats)
        )

    def check_value(self, value: str) -> bool:
        """Override DataItem method"""
        if not self.get_prop("data", "check_value", True):
            return True
        if not isinstance(value, self.type):
            return False
        return len(value) > 0

    def from_string(self, value) -> str:
        """Override DataItem method"""
        return self.add_extension(value)

    def add_extension(self, value) -> str:
        """Add extension to filename
        `value`: possible value for data item"""
        value = str(value)
        formats = self.get_prop("data", "formats")
        if len(formats) == 1 and formats[0] != "*":
            if not value.endswith("." + formats[0]) and len(value) > 0:
                return value + "." + formats[0]
        return value


class FileOpenItem(FileSaveItem):
    """
    Construct a path data item for a file to be opened
        * label [string]: name
        * formats [string (or string list)]: wildcard filter
        * default [string]: default value (optional)
        * basedir [string]: default base directory (optional)
        * help [string]: text shown in tooltip (optional)
        * check [bool]: if False, value is not checked (optional, default=True)
    """

    def check_value(self, value: str) -> bool:
        """Override DataItem method"""
        if not self.get_prop("data", "check_value", True):
            return True
        if not isinstance(value, self.type):
            return False
        return os.path.exists(value) and os.path.isfile(value)


class FilesOpenItem(FileSaveItem):
    """
    Construct a path data item for multiple files to be opened.
        * label [string]: name
        * formats [string (or string list)]: wildcard filter
        * default [string]: default value (optional)
        * basedir [string]: default base directory (optional)
        * help [string]: text shown in tooltip (optional)
        * check [bool]: if False, value is not checked (optional, default=True)
    """

    type = list

    def __init__(
        self,
        label: str,
        formats: str = "*",
        default: Optional[Union[List[str], str]] = None,
        basedir: Optional[str] = None,
        all_files_first: bool = False,
        help: str = "",
        check: bool = True,
    ) -> None:
        if isinstance(default, str):
            default = [default]
        FileSaveItem.__init__(
            self,
            label,
            formats=formats,
            default=default,
            basedir=basedir,
            all_files_first=all_files_first,
            help=help,
            check=check,
        )

    def check_value(self, value: str) -> bool:
        """Override DataItem method"""
        if not self.get_prop("data", "check_value", True):
            return True
        if value is None:
            return False
        allexist = True
        for path in value:
            allexist = allexist and os.path.exists(path) and os.path.isfile(path)
        return allexist

    def from_string(self, value: Any) -> List[str]:  # type:ignore
        """Override DataItem method"""
        if value.endswith("']") or value.endswith('"]'):
            value = eval(value)
        else:
            value = [value]
        return [self.add_extension(path) for path in value]

    def serialize(
        self,
        instance: "DataSet",
        writer: Union["HDF5Writer", "JSONWriter", "UserConfigWriter"],
    ) -> None:
        """Serialize this item"""
        value = self.get_value(instance)
        writer.write_sequence([fname.encode("utf-8") for fname in value])

    def get_value_from_reader(
        self, reader: Union["HDF5Reader", "JSONReader", "UserConfigReader"]
    ) -> List[str]:
        """Reads value from the reader object, inside the try...except
        statement defined in the base item `deserialize` method"""
        return [fname for fname in reader.read_sequence()]


class DirectoryItem(StringItem):
    """
    Construct a path data item for a directory.
        * label [string]: name
        * default [string]: default value (optional)
        * help [string]: text shown in tooltip (optional)
        * check [bool]: if False, value is not checked (optional, default=True)
    """

    def check_value(self, value: str) -> bool:
        """Override DataItem method"""
        if not self.get_prop("data", "check_value", True):
            return True
        if not isinstance(value, self.type):
            return False
        return os.path.exists(value) and os.path.isdir(value)


class FirstChoice:
    """
    Special object that means the default value of a ChoiceItem
    is the first item.
    """

    pass


class ChoiceItem(DataItem):
    """
    Construct a data item for a list of choices.
        * label [string]: name
        * choices [list, tuple or function]: string list or (key, label) list
          function of two arguments (item, value) returning a list of tuples
          (key, label, image) where image is an icon path, a QIcon instance
          or a function of one argument (key) returning a QIcon instance
        * default [-]: default label or default key (optional)
        * help [string]: text shown in tooltip (optional)
        * check [bool]: if False, value is not checked (optional, default=True)
        * radio [bool]: if True, shows radio buttons instead of a combo box
          (default is False)
    """

    def __init__(
        self,
        label: str,
        choices: Any,
        default: Optional[Union[Tuple[()], Type[FirstChoice], int]] = FirstChoice,
        help: str = "",
        check: bool = True,
        radio: bool = False,
    ) -> None:
        _choices_data: Any
        if isinstance(choices, collections.abc.Callable):  # type:ignore
            _choices_data = ItemProperty(choices)
        else:
            _choices_data = []
            for idx, choice in enumerate(choices):
                _choices_data.append(self._normalize_choice(idx, choice))
        if default is FirstChoice and not isinstance(
            choices, collections.abc.Callable  # type:ignore
        ):
            default = _choices_data[0][0]
        elif default is FirstChoice:
            default = None
        DataItem.__init__(self, label, default=default, help=help, check=check)
        self.set_prop("data", choices=_choices_data)
        self.set_prop("display", radio=radio)

    def _normalize_choice(
        self, idx: int, choice_tuple: Tuple[Any, ...]
    ) -> Union[Tuple[int, str, None], Tuple[str, str, None]]:
        if isinstance(choice_tuple, tuple):
            key, value = choice_tuple
        else:
            key = idx
            value = choice_tuple
        return (key, value, None)

    def get_string_value(self, instance: "DataSet") -> str:
        """Override DataItem method"""
        value = self.get_value(instance)
        choices = self.get_prop_value("data", instance, "choices")
        # print "ShowChoiceWidget:", choices, value
        for choice in choices:
            if choice[0] == value:
                return str(choice[1])
        else:
            return DataItem.get_string_value(self, instance)


class MultipleChoiceItem(ChoiceItem):
    """
    Construct a data item for a list of choices -- multiple choices can be selected
        * label [string]: name
        * choices [list or tuple]: string list or (key, label) list
        * default [-]: default label or default key (optional)
        * help [string]: text shown in tooltip (optional)
        * check [bool]: if False, value is not checked (optional, default=True)
    """

    def __init__(
        self,
        label: str,
        choices: List[str],
        default: Tuple[()] = (),
        help: str = "",
        check: bool = True,
    ) -> None:
        ChoiceItem.__init__(self, label, choices, default, help, check=check)
        self.set_prop("display", shape=(1, -1))

    def horizontal(self, row_nb: int = 1) -> "MultipleChoiceItem":
        """
        Method to arange choice list horizontally on `n` rows

        Example:
        nb = MultipleChoiceItem("Number", ['1', '2', '3'] ).horizontal(2)
        """
        self.set_prop("display", shape=(row_nb, -1))
        return self

    def vertical(self, col_nb: int = 1) -> "MultipleChoiceItem":
        """
        Method to arange choice list vertically on `n` columns

        Example:
        nb = MultipleChoiceItem("Number", ['1', '2', '3'] ).vertical(2)
        """
        self.set_prop("display", shape=(-1, col_nb))
        return self

    def serialize(
        self,
        instance: "DataSet",
        writer: Union["HDF5Writer", "JSONWriter", "UserConfigWriter"],
    ) -> None:
        """Serialize this item"""
        value = self.get_value(instance)
        seq = []
        _choices = self.get_prop_value("data", instance, "choices")
        for key, _label, _img in _choices:
            seq.append(key in value)
        writer.write_sequence(seq)

    def deserialize(
        self,
        instance: "DataSet",
        reader: Union["HDF5Reader", "JSONReader", "UserConfigReader"],
    ) -> None:
        """Deserialize this item"""
        try:
            flags = reader.read_sequence()
        except KeyError:
            self.set_default(instance)
        else:
            # We could have trouble with objects providing their own choice
            # function which depend on not yet deserialized values
            _choices = self.get_prop_value("data", instance, "choices")
            value = []
            for idx, flag in enumerate(flags):
                if flag:
                    value.append(_choices[idx][0])
            self.__set__(instance, value)


class ImageChoiceItem(ChoiceItem):
    """
    Construct a data item for a list of choices with images
        * label [string]: name
        * choices [list, tuple or function]: (label, image) list or
          (key, label, image) list function of two arguments (item, value)
          returning a list of tuples (key, label, image) where image is an
          icon path, a QIcon instance or a function of one argument (key)
          returning a QIcon instance
        * default [-]: default label or default key (optional)
        * help [string]: text shown in tooltip (optional)
        * check [bool]: if False, value is not checked (optional, default=True)
    """

    def _normalize_choice(
        self, idx: int, choice_tuple: Tuple[Any, ...]
    ) -> Tuple[Any, Any, Any]:
        assert isinstance(choice_tuple, tuple)
        if len(choice_tuple) == 3:
            key, value, img = choice_tuple
        else:
            key = idx
            value, img = choice_tuple
        return (key, value, img)


class FloatArrayItem(DataItem):
    """
    Construct a float array data item
        * label [string]: name
        * default [numpy.ndarray]: default value (optional)
        * help [string]: text shown in tooltip (optional)
        * format [string]: formatting string (example: '%.3f') (optional)
        * transpose [bool]: transpose matrix (display only)
        * large [bool]: view all float of the array
        * minmax [string]: "all" (default), "columns", "rows"
        * check [bool]: if False, value is not checked (optional, default=True)
    """

    def __init__(
        self,
        label: str,
        default: Optional[ndarray] = None,
        help: str = "",
        format: str = "%.3f",
        transpose: bool = False,
        minmax: str = "all",
        check: bool = True,
    ) -> None:
        DataItem.__init__(self, label, default=default, help=help, check=check)
        self.set_prop("display", format=format, transpose=transpose, minmax=minmax)

    def format_string(
        self, instance: "DataSet", value: Any, fmt: str, func: Callable
    ) -> str:
        """Override DataItem method"""
        larg = self.get_prop_value("display", instance, "large", False)
        fmt = self.get_prop_value("display", instance, "format", "%s")
        unit = self.get_prop_value("display", instance, "unit", "")
        v = func(value)
        if larg:
            text = "= ["
            for flt in v[:-1]:
                text += fmt % flt + "; "
            text += fmt % v[-1] + "]"
        else:
            text = "~= " + fmt % v.mean()
            text += " [" + fmt % v.min()
            text += " .. " + fmt % v.max()
            text += "]"
        text += " %s" % unit
        return str(text)

    def serialize(
        self,
        instance: "DataSet",
        writer: Union["HDF5Writer", "JSONWriter", "UserConfigWriter"],
    ) -> None:
        """Serialize this item"""
        value = self.get_value(instance)
        writer.write_array(value)

    def get_value_from_reader(
        self, reader: Union["HDF5Reader", "JSONReader", "UserConfigReader"]
    ) -> Any:
        """Reads value from the reader object, inside the try...except
        statement defined in the base item `deserialize` method"""
        return reader.read_array()


class ButtonItem(DataItem):
    """
    Construct a simple button that calls a method when hit
        * label [string]: text shown on the button
        * callback [function]: function with four parameters (dataset, item, value, parent)
            - dataset [DataSet]: instance of the parent dataset
            - item [DataItem]: instance of ButtonItem (i.e. self)
            - value [unspecified]: value of ButtonItem (default ButtonItem
              value or last value returned by the callback)
            - parent [QObject]: button's parent widget
        * icon [QIcon or string]: icon show on the button (optional)
          (string: icon filename as in guidata/guiqwt image search paths)
        * default [unspecified]: default value passed to the callback (optional)
        * help [string]: text shown in button's tooltip (optional)
        * check [bool]: if False, value is not checked (optional, default=True)

    The value of this item is unspecified but is passed to the callback along
    with the whole dataset. The value is assigned the callback`s return value.
    """

    def __init__(
        self,
        label: str,
        callback: Callable,
        icon: Optional[str] = None,
        default: Optional[Any] = None,
        help: str = "",
        check: bool = True,
    ) -> None:
        DataItem.__init__(self, label, default=default, help=help, check=check)
        self.set_prop("display", callback=callback)
        self.set_prop("display", icon=icon)

    def serialize(
        self,
        instance: "DataSet",
        writer: Union["HDF5Writer", "JSONWriter", "UserConfigWriter"],
    ) -> Any:
        pass

    def deserialize(
        self,
        instance: "DataSet",
        reader: Union["HDF5Reader", "JSONReader", "UserConfigReader"],
    ) -> Any:
        pass


class DictItem(ButtonItem):
    """
    Construct a dictionary data item
        * label [string]: name
        * default [dict]: default value (optional)
        * help [string]: text shown in tooltip (optional)
        * check [bool]: if False, value is not checked (optional, default=True)
    """

    def __init__(
        self,
        label: str,
        default: Optional[dict] = None,
        help: str = "",
        check: bool = True,
    ) -> None:
        def dictedit(
            instance: "DataSet", item: "DataItem", value: Any, parent: object
        ) -> Any:
            from guidata.widgets.collectionseditor import CollectionsEditor

            editor = CollectionsEditor(parent)
            value_was_none = value is None
            if value_was_none:
                value = {}
            editor.setup(value)
            if exec_dialog(editor):
                return editor.get_value()
            else:
                if value_was_none:
                    return
                return value

        ButtonItem.__init__(
            self,
            label,
            dictedit,
            icon="dictedit.png",
            default=default,
            help=help,
            check=check,
        )


class FontFamilyItem(StringItem):
    """
    Construct a font family name item
        * label [string]: name
        * default [string]: default value (optional)
        * help [string]: text shown in tooltip (optional)
    """

    pass
