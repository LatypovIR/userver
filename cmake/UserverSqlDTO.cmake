include_guard(GLOBAL)

function(_userver_prepare_sqldto)
    if(NOT USERVER_DIR)
        get_filename_component(USERVER_DIR "${CMAKE_CURRENT_LIST_DIR}/userver" DIRECTORY)
    endif()
    set(USERVER_SQLDTO_SCRIPTS_PATH "${USERVER_DIR}/scripts/sqldto")

    userver_venv_setup(
        NAME userver-sqldto
        PYTHON_OUTPUT_VAR USERVER_SQLDTO_PYTHON_BINARY
        REQUIREMENTS "${USERVER_SQLDTO_SCRIPTS_PATH}/requirements.txt"
        UNIQUE
    )
    set_property(GLOBAL PROPERTY userver_sqldto_python_binary "${USERVER_SQLDTO_PYTHON_BINARY}")
    set_property(GLOBAL PROPERTY userver_scripts_sqldto "${USERVER_SQLDTO_SCRIPTS_PATH}")
endfunction()

_userver_prepare_sqldto()


# @arg TARGET New library target name
# @param OUTPUT_DIR @required Directory to generate C++ files
# @param NAMESPACE @required C++ namespace to use
# @param PG_MIGRATIONS_DIR @optional Path to the directory with postgres .sql migration files
# @param PG_QUERIES_DIR @optional Path to the directory with postgres .sql query files
function(userver_add_sqldto_library TARGET)
    set(OPTIONS)
    set(ONE_VALUE_ARGS OUTPUT_DIR NAMESPACE PG_MIGRATIONS_DIR PG_QUERIES_DIR)
    set(MULTI_VALUE_ARGS)
    cmake_parse_arguments(ARG "${OPTIONS}" "${ONE_VALUE_ARGS}" "${MULTI_VALUE_ARGS}" ${ARGN})

    if(NOT ARG_OUTPUT_DIR)
        message(FATAL_ERROR "userver_add_sqldto_library(${TARGET}): OUTPUT_DIR is required")
    endif()
    if(NOT IS_ABSOLUTE "${ARG_OUTPUT_DIR}")
        set(ARG_OUTPUT_DIR "${CMAKE_CURRENT_BINARY_DIR}/${ARG_OUTPUT_DIR}")
    endif()
    if(NOT ARG_NAMESPACE)
        message(FATAL_ERROR "NAMESPACE argument is required")
    endif()

    set(PG_FILES)

    if(ARG_PG_MIGRATIONS_DIR)
        if(NOT IS_ABSOLUTE "${ARG_PG_MIGRATIONS_DIR}")
            set(ARG_PG_MIGRATIONS_DIR "${CMAKE_CURRENT_SOURCE_DIR}/${ARG_PG_MIGRATIONS_DIR}")
        endif()
        file(GLOB_RECURSE FILES "${ARG_PG_MIGRATIONS_DIR}/*.sql")
        list(APPEND PG_FILES ${FILES})
    endif()

    if(ARG_PG_QUERIES_DIR)
        if(NOT IS_ABSOLUTE "${ARG_PG_QUERIES_DIR}")
            set(ARG_PG_QUERIES_DIR "${CMAKE_CURRENT_SOURCE_DIR}/${ARG_PG_QUERIES_DIR}")
        endif()
        file(GLOB_RECURSE FILES "${ARG_PG_QUERIES_DIR}/*.sql")
        list(APPEND PG_FILES ${FILES})
    endif()

    set(GENERATOR_ARGS
        --namespace "${ARG_NAMESPACE}"
        --output-dir "${ARG_OUTPUT_DIR}"
    )

    if(ARG_PG_MIGRATIONS_DIR)
        list(APPEND GENERATOR_ARGS --pg-migrations-dir "${ARG_PG_MIGRATIONS_DIR}")
    endif()
    if(ARG_PG_QUERIES_DIR)
        list(APPEND GENERATOR_ARGS --pg-queries-dir "${ARG_PG_QUERIES_DIR}")
    endif()

    get_property(USERVER_SQLDTO_PYTHON_BINARY GLOBAL PROPERTY userver_sqldto_python_binary)
    get_property(USERVER_SQLDTO_SCRIPTS_PATH GLOBAL PROPERTY userver_scripts_sqldto)

    set(sqldto_include_dir ${ARG_OUTPUT_DIR}/include/${ARG_NAMESPACE})
    set(sqldto_source_dir ${ARG_OUTPUT_DIR}/src/${ARG_NAMESPACE})

    # TODO: what about new migrations file?
    set(output_files
        ${sqldto_include_dir}/pg_models.hpp
        ${sqldto_include_dir}/pg_client.hpp
        ${sqldto_include_dir}/pg_cluster.hpp
        ${sqldto_include_dir}/pg_mock.hpp
        ${sqldto_source_dir}/pg_cluster.cpp
    )

    _userver_initialize_codegen_flag()
    add_custom_command(
        OUTPUT ${output_files}
        COMMAND ${CMAKE_COMMAND} -E env "PYTHONPATH=${USERVER_SQLDTO_SCRIPTS_PATH}/.."
                ${USERVER_SQLDTO_PYTHON_BINARY}
                ${USERVER_SQLDTO_SCRIPTS_PATH}/main.py
                ${GENERATOR_ARGS}
                ${CODEGEN}
        DEPENDS ${PG_FILES}
    )
    _userver_codegen_register_files("${output_files}")

    if(NOT TARGET GTest::gmock)
        include(SetupGTest)
    endif()

    add_library(${TARGET} STATIC ${output_files})
    target_include_directories(${TARGET} PUBLIC ${ARG_OUTPUT_DIR}/include)
    target_link_libraries(${TARGET} PUBLIC userver::postgresql GTest::gmock)
endfunction()
