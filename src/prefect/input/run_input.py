from typing import (
    TYPE_CHECKING,
    Any,
    Dict,
    Generic,
    List,
    Literal,
    Optional,
    Type,
    TypeVar,
    Union,
)
from uuid import UUID, uuid4

import anyio
import orjson
import pydantic

from prefect._internal.pydantic import HAS_PYDANTIC_V2
from prefect.context import FlowRunContext
from prefect.input.actions import (
    create_flow_run_input,
    filter_flow_run_input,
    read_flow_run_input,
)
from prefect.utilities.asyncutils import sync_compatible

if TYPE_CHECKING:
    from prefect.states import State


if HAS_PYDANTIC_V2:
    from prefect._internal.pydantic.v2_schema import create_v2_schema


T = TypeVar("T", bound="RunInput")
Keyset = Dict[Union[Literal["response"], Literal["schema"]], str]
SendInputKeyset = Dict[str, Keyset]


def keyset_from_paused_state(state: "State") -> Keyset:
    """
    Get the keyset for the given Paused state.

    Args:
        - state (State): the state to get the keyset for
    """

    if not state.is_paused():
        raise RuntimeError(f"{state.type.value!r} is unsupported.")

    base_key = f"{state.name.lower()}-{str(state.state_details.pause_key)}"
    return keyset_from_base_key(base_key)


def send_input_keyset_from_run_inputs(
    run_inputs: List[Type["RunInput"]],
) -> SendInputKeyset:
    keysets = {}
    for run_input in run_inputs:
        base_key = f"{run_input.__name__.lower()}"
        keysets[run_input.__name__] = keyset_from_base_key(base_key)

    return keysets


async def send_input(input: "RunInput", flow_run_id: UUID):
    sending_flow_run_id = None

    context = FlowRunContext.get()
    if context is not None and context.flow_run is not None:
        sending_flow_run_id = context.flow_run.id

    keyset: SendInputKeyset = await read_flow_run_input(
        "keyset", flow_run_id=flow_run_id
    )
    input_keyset = keyset[input.__class__.__name__]
    base_key = input_keyset["response"]
    key = f"{base_key}-{uuid4()}"

    wrapper = InputWrapper(value=input, sending_flow_run_id=sending_flow_run_id)

    await create_flow_run_input(
        key=key, value=orjson.loads(wrapper.json()), flow_run_id=flow_run_id
    )


class get_input(Generic[T]):
    def __init__(
        self,
        run_input_cls: Type[T],
        timeout: int = 3600,
        poll_interval: int = 10,
        raise_timeout_error: bool = False,
    ):
        self.run_input_cls = run_input_cls
        self.timeout = timeout
        self.poll_interval = poll_interval
        self.exclude_keys = set()
        self.raise_timeout_error = raise_timeout_error

        self._keyset = None

    def __iter__(self):
        return self

    def __next__(self) -> "InputWrapper[T]":
        try:
            return self.next()
        except TimeoutError:
            if self.raise_timeout_error:
                raise
            raise StopIteration

    def __aiter__(self):
        return self

    async def __anext__(self) -> "InputWrapper[T]":
        try:
            return await self.next()
        except TimeoutError:
            if self.raise_timeout_error:
                raise
            raise StopAsyncIteration

    async def keyset(self):
        if self._keyset is None:
            self._keyset = await read_flow_run_input("keyset")
        return self._keyset

    async def filter_for_inputs(self, limit: int = 1):
        keyset = await self.keyset()
        input_keyset = keyset[self.run_input_cls.__name__]

        flow_run_inputs = await filter_flow_run_input(
            key_prefix=input_keyset["response"],
            limit=limit,
            exclude_keys=self.exclude_keys,
        )

        if flow_run_inputs:
            self.exclude_keys.add(*[i.key for i in flow_run_inputs])

        return flow_run_inputs

    def to_input_wrapper(self, flow_run_input) -> "InputWrapper[T]":
        decoded = flow_run_input.decoded_value
        value = decoded.pop("value")
        return InputWrapper(value=self.run_input_cls(**value), **decoded)

    @sync_compatible
    async def next(self) -> "InputWrapper[T]":
        # TODO: Right now this expects that `filter_for_inputs` will only ever
        # return one input. There's probably a world in which
        # `filter_for_inputs` prefetches some number of things, so we may need
        # to treat it as a generator and yield the inputs.
        flow_run_inputs = await self.filter_for_inputs()
        if flow_run_inputs:
            return self.to_input_wrapper(flow_run_inputs[0])

        with anyio.fail_after(self.timeout):
            initial_sleep = min(self.timeout / 2, self.poll_interval)
            await anyio.sleep(initial_sleep)
            while True:
                flow_run_inputs = await self.filter_for_inputs()
                if flow_run_inputs:
                    return self.to_input_wrapper(flow_run_inputs[0])

                await anyio.sleep(self.poll_interval)


def keyset_from_base_key(base_key: str) -> Keyset:
    """
    Get the keyset for the given base key.

    Args:
        - base_key (str): the base key to get the keyset for

    Returns:
        - Dict[str, str]: the keyset
    """
    return {
        "response": f"{base_key}-response",
        "schema": f"{base_key}-schema",
    }


class RunInput(pydantic.BaseModel):
    class Config:
        extra = "forbid"

    @classmethod
    @sync_compatible
    async def save(cls, keyset: Keyset, flow_run_id: Optional[UUID] = None):
        """
        Save the run input response to the given key.

        Args:
            - keyset (Keyset): the keyset to save the input for
            - flow_run_id (UUID, optional): the flow run ID to save the input for
        """

        if HAS_PYDANTIC_V2:
            schema = create_v2_schema(cls.__name__, model_base=cls)
        else:
            schema = cls.schema(by_alias=True)

        await create_flow_run_input(
            key=keyset["schema"], value=schema, flow_run_id=flow_run_id
        )

    @classmethod
    @sync_compatible
    async def load(cls, keyset: Keyset, flow_run_id: Optional[UUID] = None):
        """
        Load the run input response from the given key.

        Args:
            - keyset (Keyset): the keyset to load the input for
            - flow_run_id (UUID, optional): the flow run ID to load the input for
        """
        value = await read_flow_run_input(keyset["response"], flow_run_id=flow_run_id)
        return cls(**value)

    @classmethod
    def with_initial_data(cls: Type[T], **kwargs: Any) -> Type[T]:
        """
        Create a new `RunInput` subclass with the given initial data as field
        defaults.

        Args:
            - kwargs (Any): the initial data
        """
        fields = {}
        for key, value in kwargs.items():
            fields[key] = (type(value), value)
        return pydantic.create_model(cls.__name__, **fields, __base__=cls)


class InputWrapper(Generic[T], pydantic.BaseModel):
    value: T
    sending_flow_run_id: Optional[UUID] = None


InputWrapper.update_forward_refs()
