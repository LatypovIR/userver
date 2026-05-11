include_guard(GLOBAL)

function(_userver_prepare_sql2cpp)
    if(NOT USERVER_DIR)
        get_filename_component(USERVER_DIR "${CMAKE_CURRENT_LIST_DIR}/userver" DIRECTORY)
    endif()
    set(USERVER_SQL2CPP_SCRIPTS_PATH "${USERVER_DIR}/scripts/sql2cpp")

    userver_venv_setup(
        NAME userver-sql2cpp
        PYTHON_OUTPUT_VAR USERVER_SQL2CPP_PYTHON_BINARY
        REQUIREMENTS "${USERVER_SQL2CPP_SCRIPTS_PATH}/requirements.txt"
        UNIQUE
    )
    set_property(GLOBAL PROPERTY userver_sql2cpp_python_binary "${USERVER_SQL2CPP_PYTHON_BINARY}")
    set_property(GLOBAL PROPERTY userver_scripts_sql2cpp "${USERVER_SQL2CPP_SCRIPTS_PATH}")
endfunction()

_userver_prepare_sql2cpp()


# @arg TARGET New library target name
# @param SOURCE_DIR Source directory (defaults to ".")
# @param OUTPUT_DIR @required Directory to generate C++ files
# @param NAMESPACE @required C++ namespace to use
# @param PG_NAMESPACE C++ namespace to use in postgres
# @param PG_MIGRATIONS_DIR Path to the directory with postgres .sql migration files
function(userver_add_sql2cpp_library TARGET)
    set(OPTIONS)
    set(ONE_VALUE_ARGS SOURCE_DIR OUTPUT_DIR NAMESPACE PG_NAMESPACE PG_MIGRATIONS_DIR)
    set(MULTI_VALUE_ARGS)
    cmake_parse_arguments(ARG "${OPTIONS}" "${ONE_VALUE_ARGS}" "${MULTI_VALUE_ARGS}" ${ARGN})

    if(NOT ARG_OUTPUT_DIR)
        message(FATAL_ERROR "userver_add_sql2cpp_library(${TARGET}): OUTPUT_DIR is required")
    endif()
    if(NOT IS_ABSOLUTE "${ARG_OUTPUT_DIR}")
        set(ARG_OUTPUT_DIR "${CMAKE_CURRENT_BINARY_DIR}/${ARG_OUTPUT_DIR}")
    endif()
    if(NOT ARG_NAMESPACE)
        message(FATAL_ERROR "NAMESPACE argument is required")
    endif()
    if(NOT ARG_SOURCE_DIR)
        set(ARG_SOURCE_DIR ".")
    endif()
    if(NOT IS_ABSOLUTE "${ARG_SOURCE_DIR}")
        set(ARG_SOURCE_DIR "${CMAKE_CURRENT_SOURCE_DIR}/${ARG_SOURCE_DIR}")
    endif()

    set(PG_MIGRATIONS_FILES)
    if(ARG_PG_MIGRATIONS_DIR)
        if(NOT IS_ABSOLUTE "${ARG_PG_MIGRATIONS_DIR}")
            set(ARG_PG_MIGRATIONS_DIR "${ARG_SOURCE_DIR}/${ARG_PG_MIGRATIONS_DIR}")
        endif()
        file(GLOB_RECURSE PG_MIGRATIONS_FILES CONFIGURE_DEPENDS "${ARG_PG_MIGRATIONS_DIR}/*.sql")
    endif()

    set(GENERATOR_ARGS
        --namespace "${ARG_NAMESPACE}"
        --output-dir "${ARG_OUTPUT_DIR}"
    )

    if(ARG_PG_NAMESPACE)
        list(APPEND GENERATOR_ARGS --pg-namespace "${ARG_PG_NAMESPACE}")
    endif()
    if(ARG_PG_MIGRATIONS_DIR)
        list(APPEND GENERATOR_ARGS --pg-migrations-dir "${ARG_PG_MIGRATIONS_DIR}")
    endif()

    get_property(USERVER_SQL2CPP_PYTHON_BINARY GLOBAL PROPERTY userver_sql2cpp_python_binary)
    get_property(USERVER_SQL2CPP_SCRIPTS_PATH GLOBAL PROPERTY userver_scripts_sql2cpp)

    # TODO: what about new migrations file?
    set(output_files ${ARG_OUTPUT_DIR}/include/${ARG_NAMESPACE}/models.hpp)

    # TODO: No PostgreSQL installation found -- apt install postgresql
    _userver_initialize_codegen_flag()
    add_custom_command(
        OUTPUT  ${output_files}
        COMMAND ${CMAKE_COMMAND} -E env "PYTHONPATH=${USERVER_SQL2CPP_SCRIPTS_PATH}/.."
                ${USERVER_SQL2CPP_PYTHON_BINARY}
                ${USERVER_SQL2CPP_SCRIPTS_PATH}/main.py
                ${GENERATOR_ARGS}
                ${CODEGEN}
        DEPENDS ${PG_MIGRATIONS_FILES}
    )
    _userver_codegen_register_files("${output_files}")

    add_library(${TARGET} INTERFACE)
    target_sources(${TARGET} INTERFACE ${output_files})
    target_include_directories(${TARGET} INTERFACE ${ARG_OUTPUT_DIR}/include)
    target_link_libraries(${TARGET} INTERFACE userver::postgresql)
endfunction()
